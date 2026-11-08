/**
 * TypeScript reference for the idempotent-payments vectors. Same behavior as reference.py:
 * an idempotency store keyed by (tenant, operation, key) with request fingerprints, a guarded
 * payment state machine, a retry classifier, a scriptable fake processor and a payment service
 * that persists the intent before calling, treats timeouts as unknown, and reconciles pending intents.
 */
import { createHash } from "node:crypto";

export class FingerprintMismatch extends Error {}
export class InProgress extends Error {}
export class IllegalTransition extends Error {}
export class ProcessorError extends Error {
  status: number;
  constructor(status: number, message = "") {
    super(`${status} ${message}`);
    this.status = status;
  }
}
export class TimeoutError extends Error {}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function fingerprint(payload: Record<string, unknown>): string {
  return createHash("sha256").update(canonical(payload)).digest("hex");
}

interface Row { fingerprint: string; status: "in_progress" | "done"; response?: Record<string, unknown> }

export class IdempotencyStore {
  private rows = new Map<string, Row>();

  private static key(tenant: string, operation: string, key: string): string {
    return `${tenant}\u0000${operation}\u0000${key}`;
  }

  begin(tenant: string, operation: string, key: string, payload: Record<string, unknown>): ["new", null] | ["replay", Record<string, unknown>] {
    const fp = fingerprint(payload);
    const k = IdempotencyStore.key(tenant, operation, key);
    const row = this.rows.get(k);
    if (!row) {
      this.rows.set(k, { fingerprint: fp, status: "in_progress" });
      return ["new", null];
    }
    if (row.fingerprint !== fp) throw new FingerprintMismatch("same key, different request");
    if (row.status === "in_progress") throw new InProgress(key);
    return ["replay", structuredClone(row.response ?? {})];
  }

  complete(tenant: string, operation: string, key: string, response: Record<string, unknown>): void {
    const row = this.rows.get(IdempotencyStore.key(tenant, operation, key));
    if (!row) throw new Error("begin() first");
    row.response = structuredClone(response);
    row.status = "done";
  }

  get size(): number {
    return this.rows.size;
  }
}

export const TRANSITIONS: Record<string, string> = {
  "created:authorize": "authorized", "created:fail": "failed",
  "authorized:capture": "captured", "authorized:void": "voided", "authorized:fail": "failed",
  "captured:settle": "settled", "captured:refund": "refunded", "captured:partial_refund": "partially_refunded",
  "settled:refund": "refunded", "settled:partial_refund": "partially_refunded",
  "partially_refunded:refund": "refunded", "partially_refunded:partial_refund": "partially_refunded",
};

export function transition(state: string, event: string): string {
  const next = TRANSITIONS[`${state}:${event}`];
  if (!next) throw new IllegalTransition(`${event} is not allowed from ${state}`);
  return next;
}

/** null means a network error or timeout. 429 and 5xx retry; every 4xx is final. */
export function isRetryable(status: number | null): boolean {
  if (status === null) return true;
  if (status === 429) return true;
  return status >= 500 && status <= 599;
}

export class RetryPolicy {
  constructor(public maxAttempts = 3, public baseDelay = 0.2, public maxDelay = 5.0) {}
  delay(attempt: number): number {
    return Math.min(this.maxDelay, this.baseDelay * 2 ** (attempt - 1));
  }
}

/** Each call consumes one scripted outcome: "ok", "timeout", or an HTTP status such as "500".
 *  A timeout performs the charge and then throws, which is what makes the outcome unknown. */
export class FakeProcessor {
  charges = new Map<string, { id: string; amount: number; status: string }>();
  calls = 0;
  constructor(public script: string[] = []) {}

  charge(idempotencyKey: string, amount: number): { id: string; amount: number; status: string } {
    this.calls += 1;
    const outcome = this.script.length ? this.script.shift()! : "ok";
    if (outcome === "timeout") {
      if (!this.charges.has(idempotencyKey)) this.charges.set(idempotencyKey, { id: `ch_${this.charges.size + 1}`, amount, status: "succeeded" });
      throw new TimeoutError("read timed out");
    }
    if (outcome !== "ok") throw new ProcessorError(Number(outcome), "scripted");
    const existing = this.charges.get(idempotencyKey);
    if (existing) return { ...existing };
    const created = { id: `ch_${this.charges.size + 1}`, amount, status: "succeeded" };
    this.charges.set(idempotencyKey, created);
    return { ...created };
  }

  lookup(idempotencyKey: string) {
    const found = this.charges.get(idempotencyKey);
    return found ? { ...found } : null;
  }
}

type Intent = { status: string; amount: number; processor_ref: string | null };

export class PaymentService {
  intents = new Map<string, Intent>();
  sleeper: (seconds: number) => void = () => {};

  constructor(public store: IdempotencyStore, public processor: FakeProcessor, public policy = new RetryPolicy()) {}

  static operationId(tenant: string, key: string): string {
    return `${tenant}:charge:${key}`;
  }

  persistIntent(tenant: string, key: string, payload: Record<string, unknown>): string {
    const opId = PaymentService.operationId(tenant, key);
    if (!this.intents.has(opId)) this.intents.set(opId, { status: "pending", amount: payload.amount as number, processor_ref: null });
    return opId;
  }

  charge(tenant: string, key: string, payload: Record<string, unknown>): Record<string, unknown> {
    let kind: string, response: Record<string, unknown> | null;
    try {
      [kind, response] = this.store.begin(tenant, "charge", key, payload);
    } catch (e) {
      if (e instanceof InProgress) return this.resolve(tenant, key, payload);
      throw e;
    }
    if (kind === "replay") return response!;
    this.persistIntent(tenant, key, payload);
    return this.attempt(tenant, key, payload);
  }

  private attempt(tenant: string, key: string, payload: Record<string, unknown>): Record<string, unknown> {
    const opId = PaymentService.operationId(tenant, key);
    for (let attempt = 1; attempt <= this.policy.maxAttempts; attempt++) {
      try {
        const result = this.processor.charge(opId, payload.amount as number);
        return this.finish(tenant, key, { status: "succeeded", processor_ref: result.id, amount: result.amount });
      } catch (e) {
        if (e instanceof TimeoutError) return { status: "pending", operation: opId };
        if (e instanceof ProcessorError) {
          if (!isRetryable(e.status)) return this.finish(tenant, key, { status: "failed", error: e.status });
          if (attempt === this.policy.maxAttempts) return { status: "pending", operation: opId };
          this.sleeper(this.policy.delay(attempt));
          continue;
        }
        throw e;
      }
    }
    return { status: "pending", operation: opId };
  }

  private finish(tenant: string, key: string, response: Record<string, unknown>): Record<string, unknown> {
    const opId = PaymentService.operationId(tenant, key);
    const intent = this.intents.get(opId)!;
    intent.status = response.status as string;
    intent.processor_ref = (response.processor_ref as string | undefined) ?? null;
    this.store.complete(tenant, "charge", key, response);
    return { ...response };
  }

  /** A retry on an in-progress key: ask the processor before doing anything. */
  resolve(tenant: string, key: string, payload: Record<string, unknown>): Record<string, unknown> {
    const opId = PaymentService.operationId(tenant, key);
    const found = this.processor.lookup(opId);
    if (found) return this.finish(tenant, key, { status: "succeeded", processor_ref: found.id, amount: found.amount });
    return this.attempt(tenant, key, payload);
  }

  reconcilePending(): { resolved: number; pending: number } {
    let resolved = 0, pending = 0;
    for (const [opId, intent] of this.intents) {
      if (intent.status !== "pending") continue;
      const found = this.processor.lookup(opId);
      if (!found) { pending += 1; continue; }
      const [tenant, , key] = opId.split(":");
      this.finish(tenant, key, { status: "succeeded", processor_ref: found.id, amount: found.amount });
      resolved += 1;
    }
    return { resolved, pending };
  }
}
