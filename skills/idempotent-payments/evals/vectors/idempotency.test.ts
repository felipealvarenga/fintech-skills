/**
 * Test vectors for idempotent-payments (TypeScript). Same cases as test_idempotency.py.
 *
 * Run against the reference: `npx vitest run skills/idempotent-payments`
 * Run against your module:   `IDEMPOTENCY_SOLUTION_TS=/abs/path/to/payments.ts npx vitest run skills/idempotent-payments`
 */
import { describe, expect, it } from "vitest";

const modulePath = process.env.IDEMPOTENCY_SOLUTION_TS ?? "./reference.ts";
const m = await import(modulePath);

const PAY = { amount: 1999, currency: "BRL", customer: "cus_1" };

function service(script?: string[], maxAttempts?: number) {
  const proc = new m.FakeProcessor(script);
  const svc = new m.PaymentService(new m.IdempotencyStore(), proc, maxAttempts ? new m.RetryPolicy(maxAttempts) : undefined);
  return { svc, proc };
}

describe("idempotency store", () => {
  it("same key twice charges once and replays the response", () => {
    const { svc, proc } = service();
    const first = svc.charge("t1", "k1", PAY);
    const second = svc.charge("t1", "k1", PAY);
    expect(second).toEqual(first);
    expect(first.status).toBe("succeeded");
    expect(proc.calls).toBe(1);
    expect(proc.charges.size).toBe(1);
  });

  it("same key with a different payload is refused", () => {
    const { svc, proc } = service();
    svc.charge("t1", "k1", PAY);
    expect(() => svc.charge("t1", "k1", { ...PAY, amount: 2999 })).toThrow(m.FingerprintMismatch);
    expect(proc.calls).toBe(1);
  });

  it("keys are scoped by tenant and operation", () => {
    const store = new m.IdempotencyStore();
    expect(store.begin("t1", "charge", "k", PAY)[0]).toBe("new");
    expect(store.begin("t2", "charge", "k", PAY)[0]).toBe("new");
    expect(store.begin("t1", "refund", "k", PAY)[0]).toBe("new");
    expect(store.size).toBe(3);
  });

  it("a concurrent duplicate sees in-progress, then replays", () => {
    const store = new m.IdempotencyStore();
    expect(store.begin("t1", "charge", "k", PAY)).toEqual(["new", null]);
    expect(() => store.begin("t1", "charge", "k", PAY)).toThrow(m.InProgress);
    store.complete("t1", "charge", "k", { status: "succeeded" });
    expect(store.begin("t1", "charge", "k", PAY)).toEqual(["replay", { status: "succeeded" }]);
  });

  it("stores a copy of the response", () => {
    const store = new m.IdempotencyStore();
    store.begin("t1", "charge", "k", PAY);
    const resp: Record<string, unknown> = { status: "succeeded", ref: "ch_1" };
    store.complete("t1", "charge", "k", resp);
    resp.ref = "mutated";
    expect((store.begin("t1", "charge", "k", PAY)[1] as Record<string, unknown>).ref).toBe("ch_1");
  });
});

describe("unknown outcome and recovery", () => {
  it("timeout is unknown; a same-key retry charges once", () => {
    const { svc, proc } = service(["timeout", "ok"]);
    const first = svc.charge("t1", "k1", PAY);
    expect(first.status).toBe("pending");
    expect(proc.charges.size).toBe(1);
    const second = svc.charge("t1", "k1", PAY);
    expect(second.status).toBe("succeeded");
    expect(proc.charges.size).toBe(1);
    expect(svc.intents.get(m.PaymentService.operationId("t1", "k1")).status).toBe("succeeded");
  });

  it("persist before call: the reconciler resolves from the processor", () => {
    const { svc, proc } = service(["timeout"]);
    svc.charge("t1", "k1", PAY);
    expect(svc.reconcilePending()).toEqual({ resolved: 1, pending: 0 });
    expect(proc.charges.size).toBe(1);
    expect(svc.charge("t1", "k1", PAY).status).toBe("succeeded");
    expect(proc.calls).toBe(1);
  });

  it("a crash between persist and call leaves a pending intent", () => {
    const { svc, proc } = service();
    svc.persistIntent("t1", "k9", PAY);
    expect(svc.reconcilePending()).toEqual({ resolved: 0, pending: 1 });
    expect(proc.calls).toBe(0);
  });
});

describe("retries", () => {
  it("a validation error is final and replays as the same failure", () => {
    const { svc, proc } = service(["400"]);
    const first = svc.charge("t1", "k1", PAY);
    expect(first.status).toBe("failed");
    expect(first.error).toBe(400);
    expect(proc.calls).toBe(1);
    expect(svc.charge("t1", "k1", PAY)).toEqual(first);
  });

  it("server errors retry with backoff and the same key", () => {
    const delays: number[] = [];
    const { svc, proc } = service(["500", "503", "ok"], 3);
    svc.sleeper = (s: number) => delays.push(s);
    const result = svc.charge("t1", "k1", PAY);
    expect(result.status).toBe("succeeded");
    expect(proc.calls).toBe(3);
    expect(proc.charges.size).toBe(1);
    expect(delays).toEqual([0.2, 0.4]);
  });

  it("retries are bounded", () => {
    const { svc, proc } = service(["500", "500", "500", "ok"], 3);
    expect(svc.charge("t1", "k1", PAY).status).toBe("pending");
    expect(proc.calls).toBe(3);
  });

  it.each([
    [null, true], [429, true], [500, true], [503, true], [400, false], [402, false], [404, false], [422, false], [200, false],
  ])("isRetryable(%s) = %s", (status, retryable) => {
    expect(m.isRetryable(status)).toBe(retryable);
  });
});

describe("state machine", () => {
  it("walks the happy path and guards illegal transitions", () => {
    let s = "created";
    for (const event of ["authorize", "capture", "settle"]) s = m.transition(s, event);
    expect(s).toBe("settled");
    expect(m.transition("settled", "partial_refund")).toBe("partially_refunded");
    expect(m.transition("partially_refunded", "refund")).toBe("refunded");
    expect(() => m.transition("captured", "capture")).toThrow(m.IllegalTransition);
    expect(() => m.transition("refunded", "refund")).toThrow(m.IllegalTransition);
    expect(() => m.transition("created", "capture")).toThrow(m.IllegalTransition);
  });
});
