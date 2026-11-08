/**
 * Test vectors for double-entry-ledger (TypeScript). Same cases as test_ledger.py.
 *
 * Run against the reference: `npx vitest run skills/double-entry-ledger`
 * Run against your module:   `LEDGER_SOLUTION_TS=/abs/path/to/ledger.ts npx vitest run skills/double-entry-ledger`
 *
 * The module must export posting(account, side, amount, currency?), a Ledger class with post, close,
 * balance, reverse and trialBalance, and throw on invalid input. Dates are ISO strings.
 */
import { describe, expect, it } from "vitest";

const modulePath = process.env.LEDGER_SOLUTION_TS ?? "./reference.ts";
const m = await import(modulePath);

const D = "2026-03-10";
const P = (account: string, side: "debit" | "credit", amount: number, ccy = "BRL") => m.posting(account, side, amount, ccy);

function capture(id = "e1", ref = "pay_1", on = D) {
  return { id, effectiveDate: on, postings: [P("1020", "debit", 9710), P("5010", "debit", 290), P("2010", "credit", 9500), P("4010", "credit", 500)], externalRef: ref, description: "capture" };
}

function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

describe("posting", () => {
  it("posts a balanced entry and derives balances", () => {
    const L = new m.Ledger();
    L.post(capture());
    expect(L.balance("1020", "BRL")).toBe(9710);
    expect(L.balance("2010", "BRL")).toBe(-9500);
    expect(L.balance("4010", "BRL")).toBe(-500);
    expect(L.balance("5010", "BRL")).toBe(290);
  });

  it("rejects unbalanced, single-posting and non-positive entries", () => {
    const L = new m.Ledger();
    expect(() => L.post({ id: "e", effectiveDate: D, postings: [P("1020", "debit", 100), P("2010", "credit", 99)], externalRef: "r1" })).toThrow();
    expect(() => L.post({ id: "e", effectiveDate: D, postings: [P("1020", "debit", 100)], externalRef: "r2" })).toThrow();
    for (const amount of [0, -1, 1.5]) {
      expect(() => L.post({ id: "e", effectiveDate: D, postings: [P("1020", "debit", amount), P("2010", "credit", amount)], externalRef: `r${amount}` })).toThrow();
    }
  });

  it("balances per currency and refuses cross-currency netting", () => {
    const L = new m.Ledger();
    L.post({ id: "fx", effectiveDate: D, postings: [P("1010", "debit", 500, "USD"), P("3010", "credit", 500, "USD"), P("3010", "debit", 2500, "BRL"), P("1011", "credit", 2500, "BRL")], externalRef: "fx1" });
    expect(() => L.post({ id: "bad", effectiveDate: D, postings: [P("1010", "debit", 500, "USD"), P("1011", "credit", 2500, "BRL")], externalRef: "fx2" })).toThrow();
  });

  it("freezes entries and postings", () => {
    const L = new m.Ledger();
    const e = L.post(capture());
    expect(Object.isFrozen(e)).toBe(true);
    expect(Object.isFrozen(e.postings[0])).toBe(true);
    expect(() => { (e.postings[0] as { amount: number }).amount = 1; }).toThrow();
  });
});

describe("reversal, periods, idempotency", () => {
  it("a reversal nets every account to its prior balance", () => {
    const L = new m.Ledger();
    L.post(capture());
    L.reverse("e1", D, "e1r", "pay_1_rev");
    for (const acct of ["1020", "5010", "2010", "4010"]) expect(L.balance(acct, "BRL")).toBe(0);
    expect(L.entries.at(-1).reverses).toBe("e1");
  });

  it("refuses backdated entries after close and corrects in the open period", () => {
    const L = new m.Ledger();
    L.post(capture());
    L.close("2026-03-31");
    expect(() => L.post(capture("e2", "pay_2", "2026-03-31"))).toThrow();
    L.post(capture("e3", "pay_3", "2026-04-01"));
    const rev = L.reverse("e1", "2026-04-02", "e1r", "pay_1_rev");
    expect(rev.effectiveDate).toBe("2026-04-02");
  });

  it("the same external reference is idempotent", () => {
    const L = new m.Ledger();
    const first = L.post(capture());
    const again = L.post(capture("e1-dup", "pay_1"));
    expect(again).toBe(first);
    expect(L.entries).toHaveLength(1);
    expect(L.balance("1020", "BRL")).toBe(9710);
  });

  it("as-of balances use the effective date", () => {
    const L = new m.Ledger();
    L.post(capture("a", "p1", "2026-01-05"));
    L.post(capture("b", "p2", "2026-02-05"));
    expect(L.balance("1020", "BRL", "2026-01-31")).toBe(9710);
    expect(L.balance("1020", "BRL")).toBe(19420);
  });

  it("the trial balance is zero after random balanced entries", () => {
    const L = new m.Ledger();
    const rnd = seeded(3);
    const accounts = ["1010", "1020", "2010", "4010", "5010"];
    for (let i = 0; i < 300; i++) {
      const amt = 1 + Math.floor(rnd() * 1_000_000);
      const a = accounts[Math.floor(rnd() * accounts.length)];
      let b = accounts[Math.floor(rnd() * accounts.length)];
      while (b === a) b = accounts[Math.floor(rnd() * accounts.length)];
      const split = 1 + Math.floor(rnd() * amt);
      const postings = amt - split > 0
        ? [P(a, "debit", amt), P(b, "credit", split), P("4010", "credit", amt - split)]
        : [P(a, "debit", amt), P(b, "credit", amt)];
      L.post({ id: `e${i}`, effectiveDate: D, postings, externalRef: `ref${i}` });
    }
    const [debits, credits] = L.trialBalance();
    expect(debits).toBe(credits);
    expect(accounts.reduce((s, acc) => s + L.balance(acc, "BRL"), 0)).toBe(0);
  });
});
