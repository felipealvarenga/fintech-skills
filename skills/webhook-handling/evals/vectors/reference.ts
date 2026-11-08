/**
 * TypeScript reference for the webhook-handling vectors. Same behavior as reference.py:
 * HMAC-SHA256 over `${timestamp}.${rawBody}`, a `t=<ts>,v1=<hex>` header, a timestamp tolerance,
 * several active secrets, dedupe by event id, monotonic state and the response status rules.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

export class BadSignature extends Error {}

function mac(secret: string, rawBody: Buffer, timestamp: number): string {
  return createHmac("sha256", secret).update(`${timestamp}.`).update(rawBody).digest("hex");
}

export function sign(secret: string, rawBody: Buffer, timestamp: number): string {
  return `t=${timestamp},v1=${mac(secret, rawBody, timestamp)}`;
}

/** Any malformed header is BadSignature, never a TypeError: the endpoint answers 400. */
function parse(header: string): { ts: number; sigs: string[] } {
  if (typeof header !== "string") throw new BadSignature("missing or non-text signature header");
  let ts: number | undefined;
  const sigs: string[] = [];
  for (const part of header.split(",")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (k === "t") {
      if (!/^\d+$/.test(v)) throw new BadSignature("malformed timestamp");
      ts = Number(v);
    } else if (k === "v1") sigs.push(v);
  }
  if (ts === undefined || !sigs.length) throw new BadSignature("malformed header");
  return { ts, sigs };
}

/** Throws BadSignature unless one active secret signs the raw body within the tolerance. */
export function verify(header: string, rawBody: unknown, secrets: string[], now: number, tolerance = 300): void {
  if (!Buffer.isBuffer(rawBody)) throw new BadSignature("verify the raw bytes, not a parsed body");
  const { ts, sigs } = parse(header);
  if (Math.abs(now - ts) > tolerance) throw new BadSignature("timestamp outside tolerance");
  for (const secret of secrets) {
    const expected = Buffer.from(mac(secret, rawBody, ts), "hex");
    for (const candidate of sigs) {
      if (!/^[0-9a-f]+$/i.test(candidate)) continue;
      const got = Buffer.from(candidate, "hex");
      if (got.length === expected.length && timingSafeEqual(got, expected)) return;
    }
  }
  throw new BadSignature("no active secret matches");
}

export class EventStore {
  events = new Map<string, { payload: unknown; status: string; error?: string | null }>();

  /** True the first time an event id is seen. */
  record(eventId: string, payload: unknown): boolean {
    if (this.events.has(eventId)) return false;
    this.events.set(eventId, { payload: structuredClone(payload), status: "stored" });
    return true;
  }

  mark(eventId: string, status: string, error: string | null = null): void {
    const row = this.events.get(eventId);
    if (!row) throw new Error("unknown event");
    row.status = status;
    row.error = error;
  }
}

export const ORDER: Record<string, number> = { created: 0, authorized: 1, captured: 2, settled: 3, refunded: 4 };

/** Never regress: an older state arriving late leaves the current state alone. */
export function applyState(current: string, incoming: string): string {
  if (!(incoming in ORDER) || !(current in ORDER)) throw new Error("unknown state");
  return ORDER[incoming] > ORDER[current] ? incoming : current;
}

/** 400 for a bad signature, 500 only when storage failed, 200 otherwise (handled or not). */
export function responseStatus(opts: { signatureOk: boolean; stored: boolean; handled?: boolean }): number {
  if (!opts.signatureOk) return 400;
  if (!opts.stored) return 500;
  return 200;
}

export function receive(
  header: string,
  rawBody: Buffer,
  eventId: string,
  payload: unknown,
  opts: { secrets: string[]; now: number; store: EventStore; tolerance?: number },
): [number, string] {
  try {
    verify(header, rawBody, opts.secrets, opts.now, opts.tolerance ?? 300);
  } catch (e) {
    if (e instanceof BadSignature) return [responseStatus({ signatureOk: false, stored: false }), "rejected"];
    throw e;
  }
  let fresh: boolean;
  try {
    fresh = opts.store.record(eventId, payload);
  } catch {
    return [responseStatus({ signatureOk: true, stored: false }), "storage_failed"];
  }
  return [responseStatus({ signatureOk: true, stored: true }), fresh ? "queued" : "duplicate"];
}
