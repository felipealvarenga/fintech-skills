/**
 * TypeScript reference for the double-entry-ledger vectors. Same behavior as reference.py:
 * balanced entries per currency, positive postings with a side, frozen entries, derived balances,
 * reversal, period close and idempotent posting by external reference.
 */

export class Unbalanced extends Error {}
export class InvalidPosting extends Error {}
export class PeriodClosed extends Error {}

export type Side = "debit" | "credit";

export interface Posting {
  readonly account: string;
  readonly side: Side;
  readonly amount: number; // minor units, > 0
  readonly currency: string;
}

export interface Entry {
  readonly id: string;
  readonly effectiveDate: string; // ISO date, YYYY-MM-DD
  readonly postings: readonly Posting[];
  readonly externalRef: string;
  readonly description?: string;
  readonly reverses?: string | null;
}

export function posting(account: string, side: Side, amount: number, currency = "BRL"): Posting {
  return Object.freeze({ account, side, amount, currency });
}

export function entry(fields: Entry): Entry {
  return Object.freeze({ ...fields, postings: Object.freeze(fields.postings.map((p) => Object.freeze({ ...p }))) });
}

export function validate(e: Entry): void {
  if (e.postings.length < 2) throw new InvalidPosting("an entry needs at least two postings");
  const sums = new Map<string, number>();
  for (const p of e.postings) {
    if (p.side !== "debit" && p.side !== "credit") throw new InvalidPosting(`bad side ${p.side}`);
    if (!Number.isInteger(p.amount) || p.amount <= 0) throw new InvalidPosting("posting amounts must be positive integers");
    sums.set(p.currency, (sums.get(p.currency) ?? 0) + (p.side === "debit" ? p.amount : -p.amount));
  }
  for (const [ccy, net] of sums) if (net !== 0) throw new Unbalanced(`${ccy} debits and credits differ by ${net}`);
}

export class Ledger {
  readonly entries: Entry[] = [];
  closedThrough: string | null = null;
  private byRef = new Map<string, Entry>();

  post(e: Entry): Entry {
    const existing = this.byRef.get(e.externalRef);
    if (existing) return existing;
    validate(e);
    if (this.closedThrough !== null && e.effectiveDate <= this.closedThrough) {
      throw new PeriodClosed(`${e.effectiveDate} is on or before ${this.closedThrough}`);
    }
    const frozen = entry(e);
    this.entries.push(frozen);
    this.byRef.set(frozen.externalRef, frozen);
    return frozen;
  }

  close(through: string): void {
    this.closedThrough = through;
  }

  /** Net debit balance: debits minus credits. Credit-normal accounts read negative. */
  balance(account: string, currency: string, asOf: string | null = null): number {
    let total = 0;
    for (const e of this.entries) {
      if (asOf !== null && e.effectiveDate > asOf) continue;
      for (const p of e.postings) {
        if (p.account === account && p.currency === currency) total += p.side === "debit" ? p.amount : -p.amount;
      }
    }
    return total;
  }

  reverse(entryId: string, on: string, newId: string, externalRef: string): Entry {
    const original = this.entries.find((e) => e.id === entryId);
    if (!original) throw new Error(`unknown entry ${entryId}`);
    const flipped = original.postings.map((p) => posting(p.account, p.side === "debit" ? "credit" : "debit", p.amount, p.currency));
    return this.post({ id: newId, effectiveDate: on, postings: flipped, externalRef, description: `reversal of ${entryId}`, reverses: entryId });
  }

  trialBalance(): [number, number] {
    let debits = 0, credits = 0;
    for (const e of this.entries) for (const p of e.postings) {
      if (p.side === "debit") debits += p.amount; else credits += p.amount;
    }
    return [debits, credits];
  }
}
