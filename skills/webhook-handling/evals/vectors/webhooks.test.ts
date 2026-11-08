/**
 * Test vectors for webhook-handling (TypeScript). Same cases as test_webhooks.py.
 *
 * Run against the reference: `npx vitest run skills/webhook-handling`
 * Run against your module:   `WEBHOOK_SOLUTION_TS=/abs/path/to/webhooks.ts npx vitest run skills/webhook-handling`
 *
 * The module must export sign, verify, BadSignature, EventStore, applyState, responseStatus, receive.
 */
import { describe, expect, it } from "vitest";

const modulePath = process.env.WEBHOOK_SOLUTION_TS ?? "./reference.ts";
const m = await import(modulePath);

const SECRET = "whsec_test_1";
const NOW = 1_800_000_000;
const BODY = Buffer.from('{"id":"evt_1","type":"payment_intent.succeeded","data":{"object":{"id":"pi_1","status":"succeeded"}}}');

describe("signature verification", () => {
  it("passes a valid signature", () => {
    expect(() => m.verify(m.sign(SECRET, BODY, NOW), BODY, [SECRET], NOW)).not.toThrow();
  });

  it("fails on a wrong secret, a tampered body and a re-serialized body", () => {
    expect(() => m.verify(m.sign("whsec_other", BODY, NOW), BODY, [SECRET], NOW)).toThrow(m.BadSignature);
    const header = m.sign(SECRET, BODY, NOW);
    const tampered = Buffer.from(BODY.toString().replace("succeeded", "failed"));
    expect(() => m.verify(header, tampered, [SECRET], NOW)).toThrow(m.BadSignature);
    const pretty = Buffer.from(JSON.stringify(JSON.parse(BODY.toString()), null, 2));
    expect(() => m.verify(header, pretty, [SECRET], NOW)).toThrow(m.BadSignature);
  });

  it("refuses a non-buffer body", () => {
    expect(() => m.verify(m.sign(SECRET, BODY, NOW), BODY.toString(), [SECRET], NOW)).toThrow(m.BadSignature);
  });

  it.each([
    [0, true], [299, true], [300, true], [301, false], [-301, false], [86400, false],
  ])("timestamp skew %i ok=%s", (skew, ok) => {
    const header = m.sign(SECRET, BODY, NOW - skew);
    if (ok) expect(() => m.verify(header, BODY, [SECRET], NOW)).not.toThrow();
    else expect(() => m.verify(header, BODY, [SECRET], NOW)).toThrow(m.BadSignature);
  });

  it("accepts either of two active secrets during rotation and only the new one after", () => {
    const oldS = "whsec_old", newS = "whsec_new";
    expect(() => m.verify(m.sign(oldS, BODY, NOW), BODY, [newS, oldS], NOW)).not.toThrow();
    expect(() => m.verify(m.sign(newS, BODY, NOW), BODY, [newS, oldS], NOW)).not.toThrow();
    expect(() => m.verify(m.sign(oldS, BODY, NOW), BODY, [newS], NOW)).toThrow(m.BadSignature);
  });

  it.each(["", "t=abc,v1=00", "v1=00", `t=${NOW}`])("rejects malformed header %j", (header) => {
    expect(() => m.verify(header, BODY, [SECRET], NOW)).toThrow();
  });
});

describe("dedupe, ordering, status codes", () => {
  it("records an event id once", () => {
    const store = new m.EventStore();
    expect(store.record("evt_1", { type: "x" })).toBe(true);
    expect(store.record("evt_1", { type: "x" })).toBe(false);
    expect(store.record("evt_2", { type: "x" })).toBe(true);
    expect(store.events.size).toBe(2);
  });

  it("never regresses state on out-of-order events", () => {
    expect(m.applyState("created", "captured")).toBe("captured");
    expect(m.applyState("captured", "authorized")).toBe("captured");
    expect(m.applyState("captured", "captured")).toBe("captured");
    expect(m.applyState("settled", "refunded")).toBe("refunded");
    expect(() => m.applyState("captured", "paid-ish")).toThrow();
  });

  it("returns the status code that drives provider retries", () => {
    expect(m.responseStatus({ signatureOk: false, stored: false })).toBe(400);
    expect(m.responseStatus({ signatureOk: true, stored: false })).toBe(500);
    expect(m.responseStatus({ signatureOk: true, stored: true, handled: true })).toBe(200);
    expect(m.responseStatus({ signatureOk: true, stored: true, handled: false })).toBe(200);
  });

  it("stores, acknowledges and dedupes on the receive path", () => {
    const store = new m.EventStore();
    const header = m.sign(SECRET, BODY, NOW);
    const payload = JSON.parse(BODY.toString());
    expect(m.receive(header, BODY, "evt_1", payload, { secrets: [SECRET], now: NOW, store })).toEqual([200, "queued"]);
    expect(m.receive(header, BODY, "evt_1", payload, { secrets: [SECRET], now: NOW, store })).toEqual([200, "duplicate"]);
    expect(m.receive("t=1,v1=00", BODY, "evt_2", {}, { secrets: [SECRET], now: NOW, store })).toEqual([400, "rejected"]);
    expect(store.events.has("evt_2")).toBe(false);
  });

  it("returns 500 when storage fails so the provider retries", () => {
    class Broken extends m.EventStore {
      record(): boolean {
        throw new Error("db down");
      }
    }
    const header = m.sign(SECRET, BODY, NOW);
    expect(m.receive(header, BODY, "evt_1", {}, { secrets: [SECRET], now: NOW, store: new Broken() })).toEqual([500, "storage_failed"]);
  });
});
