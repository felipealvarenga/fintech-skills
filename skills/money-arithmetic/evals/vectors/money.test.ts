/**
 * Test vectors for money-arithmetic (TypeScript). Same cases as test_money.py.
 *
 * Run against the reference: `npx vitest run skills/money-arithmetic`
 * Run against your module:   `MONEY_SOLUTION_TS=/abs/path/to/money.ts npx vitest run skills/money-arithmetic`
 *
 * The module under test must export toMinor, fromMinor, add, allocate, applyRate and convert,
 * and throw on unknown currencies, invalid amounts and currency mismatches.
 */
import { describe, expect, it } from "vitest";

const modulePath = process.env.MONEY_SOLUTION_TS ?? "./reference.ts";
const m = await import(modulePath);

function seeded(seed: number) {
  // deterministic LCG, enough for property-style loops
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

describe("toMinor and fromMinor", () => {
  it.each([
    ["12.34", "USD", 1234],
    ["0.01", "BRL", 1],
    ["-0.01", "EUR", -1],
    ["5", "JPY", 5],
    ["12.345", "BHD", 12345],
    ["1000000.00", "USD", 100000000],
  ])("toMinor(%s, %s) = %i", (amount, ccy, minor) => {
    expect(m.toMinor(amount, ccy)).toBe(minor);
    expect(Number.isInteger(m.toMinor(amount, ccy))).toBe(true);
  });

  it.each([
    ["12.345", "USD"], ["1.5", "JPY"], ["0.0001", "BHD"], ["NaN", "USD"], ["Infinity", "USD"], ["abc", "USD"], ["12,34", "USD"],
  ])("refuses %s %s", (amount, ccy) => {
    expect(() => m.toMinor(amount, ccy)).toThrow();
  });

  it("refuses unknown currencies", () => {
    expect(() => m.toMinor("1.00", "XXX")).toThrow();
    expect(() => m.fromMinor(100, "ZZZ")).toThrow();
  });

  it.each([
    [1234, "USD", "12.34"], [5, "USD", "0.05"], [-1, "USD", "-0.01"], [5, "JPY", "5"], [12345, "BHD", "12.345"], [0, "BRL", "0.00"],
  ])("fromMinor(%i, %s) = %s", (minor, ccy, text) => {
    expect(m.fromMinor(minor, ccy)).toBe(text);
  });

  it.each(["USD", "JPY", "BHD"])("round trips in %s", (ccy) => {
    const rnd = seeded(7);
    for (let i = 0; i < 200; i++) {
      const x = Math.floor(rnd() * 2e9) - 1e9;
      expect(m.toMinor(m.fromMinor(x, ccy), ccy)).toBe(x);
    }
  });
});

describe("add", () => {
  it("adds the same currency and refuses mixed currencies", () => {
    expect(m.add([100, "USD"], [250, "USD"])).toEqual([350, "USD"]);
    expect(() => m.add([100, "USD"], [100, "BRL"])).toThrow();
  });
});

describe("allocate", () => {
  it.each([
    [100, [1, 1, 1], [34, 33, 33]],
    [10, [1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1]],
    [-100, [1, 1, 1], [-34, -33, -33]],
    [100, [1, 0, 1], [50, 0, 50]],
    [1, [1, 1], [1, 0]],
    [0, [3, 2], [0, 0]],
    [1000, [70, 30], [700, 300]],
    [1001, [70, 30], [701, 300]],
  ])("allocate(%i, %j) = %j", (amount, ratios, expected) => {
    expect(m.allocate(amount, ratios)).toEqual(expected);
  });

  it("preserves the sum and stays within one unit of the exact share", () => {
    const rnd = seeded(42);
    for (let i = 0; i < 500; i++) {
      const amount = Math.floor(rnd() * 2e7) - 1e7;
      const n = 1 + Math.floor(rnd() * 9);
      const ratios = Array.from({ length: n }, () => Math.floor(rnd() * 51));
      if (ratios.every((r) => r === 0)) ratios[0] = 1;
      const parts = m.allocate(amount, ratios);
      const total = ratios.reduce((s, r) => s + r, 0);
      expect(parts).toHaveLength(n);
      expect(parts.reduce((s, p) => s + p, 0)).toBe(amount);
      parts.forEach((part, k) => {
        expect(Math.abs(part - (amount * ratios[k]) / total)).toBeLessThan(1 + 1e-9);
        if (ratios[k] === 0) expect(part).toBe(0);
      });
    }
  });

  it("refuses bad ratios", () => {
    expect(() => m.allocate(100, [])).toThrow();
    expect(() => m.allocate(100, [0, 0])).toThrow();
    expect(() => m.allocate(100, [1, -1])).toThrow();
  });
});

describe("applyRate and convert", () => {
  it("makes the rounding policy visible", () => {
    expect(m.applyRate(1000, "0.0315")).toBe(32);
    expect(m.applyRate(1000, "0.0325", "HALF_EVEN")).toBe(32);
    expect(m.applyRate(1000, "0.0325", "HALF_UP")).toBe(33);
    expect(m.applyRate(-1000, "0.0325", "HALF_UP")).toBe(-33);
    expect(Number.isInteger(m.applyRate(1000, "0.0315"))).toBe(true);
  });

  it.each([
    [1000, "USD", "BRL", "5.1234", 5123],
    [1000, "USD", "JPY", "150.5", 1505],
    [1505, "JPY", "USD", "0.0066445", 1000],
    [12345, "BHD", "USD", "2.65", 3271],
    [100, "USD", "USD", "1", 100],
  ])("convert(%i, %s, %s, %s) = %i", (amount, src, dst, rate, expected) => {
    const out = m.convert(amount, src, dst, rate);
    expect(out).toBe(expected);
    expect(Number.isInteger(out)).toBe(true);
  });
});
