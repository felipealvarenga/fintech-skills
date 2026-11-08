/**
 * TypeScript reference for the money-arithmetic vectors.
 *
 * Amounts are integers in minor units (number, within Number.MAX_SAFE_INTEGER) with an ISO 4217
 * code. Rates are decimal strings. No floating-point arithmetic touches an amount: rates are
 * handled as scaled BigInt and rounded once with a named policy.
 */

export const EXPONENTS: Record<string, number> = {
  USD: 2, EUR: 2, BRL: 2, GBP: 2, CAD: 2, AUD: 2, MXN: 2,
  JPY: 0, KRW: 0, CLP: 0, ISK: 0,
  BHD: 3, KWD: 3, TND: 3, JOD: 3, OMR: 3,
};

export type Rounding = "HALF_EVEN" | "HALF_UP";

export class UnknownCurrency extends Error {}
export class CurrencyMismatch extends Error {}
export class InvalidAmount extends Error {}

export function exponent(currency: string): number {
  const exp = EXPONENTS[currency];
  if (exp === undefined) throw new UnknownCurrency(currency);
  return exp;
}

/** Parse a decimal string into a scaled integer: value = digits / 10^scale. */
function parseDecimal(text: string): { digits: bigint; scale: number } {
  const m = /^([+-])?(\d+)(?:\.(\d+))?$/.exec(text.trim());
  if (!m) throw new InvalidAmount(text);
  const sign = m[1] === "-" ? -1n : 1n;
  const frac = m[3] ?? "";
  return { digits: sign * BigInt(m[2] + frac), scale: frac.length };
}

/** Divide num by den (den > 0) rounding to an integer with the named policy. */
function divRound(num: bigint, den: bigint, rounding: Rounding): bigint {
  const negative = num < 0n;
  const abs = negative ? -num : num;
  const q = abs / den;
  const r = abs % den;
  const twice = r * 2n;
  let up = false;
  if (twice > den) up = true;
  else if (twice === den) up = rounding === "HALF_UP" ? true : q % 2n === 1n;
  const result = up ? q + 1n : q;
  return negative ? -result : result;
}

function toSafeNumber(value: bigint): number {
  if (value > BigInt(Number.MAX_SAFE_INTEGER) || value < -BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new InvalidAmount("amount exceeds the safe integer range");
  }
  return Number(value);
}

export function toMinor(amount: string, currency: string): number {
  const exp = exponent(currency);
  const { digits, scale } = parseDecimal(amount);
  if (scale <= exp) return toSafeNumber(digits * 10n ** BigInt(exp - scale));
  const den = 10n ** BigInt(scale - exp);
  if (digits % den !== 0n) throw new InvalidAmount(`${amount} has more decimals than ${currency} allows (${exp})`);
  return toSafeNumber(digits / den);
}

export function fromMinor(minor: number, currency: string): string {
  const exp = exponent(currency);
  if (!Number.isSafeInteger(minor)) throw new InvalidAmount(String(minor));
  const sign = minor < 0 ? "-" : "";
  const digits = String(Math.abs(minor)).padStart(exp + 1, "0");
  if (exp === 0) return sign + digits;
  return `${sign}${digits.slice(0, -exp)}.${digits.slice(-exp)}`;
}

export type Money = [number, string];

export function add(a: Money, b: Money): Money {
  if (a[1] !== b[1]) throw new CurrencyMismatch(`${a[1]} != ${b[1]}`);
  exponent(a[1]);
  return [a[0] + b[0], a[1]];
}

export function allocate(amount: number, ratios: number[]): number[] {
  if (!ratios.length || ratios.some((r) => !Number.isInteger(r) || r < 0)) {
    throw new Error("ratios must be a non-empty list of non-negative integers");
  }
  const total = ratios.reduce((s, r) => s + r, 0);
  if (total === 0) throw new Error("ratios must not all be zero");
  // `x === 0 ? 0 : -x` avoids JavaScript's negative zero, which Object.is and strict test
  // matchers distinguish from 0.
  if (amount < 0) return allocate(-amount, ratios).map((x) => (x === 0 ? 0 : -x));
  const A = BigInt(amount);
  const T = BigInt(total);
  const shares = ratios.map((r) => (A * BigInt(r)) / T);
  const remainders = ratios.map((r) => (A * BigInt(r)) % T);
  let leftover = A - shares.reduce((s, x) => s + x, 0n);
  const order = ratios.map((_, i) => i).sort((i, j) => (remainders[j] > remainders[i] ? 1 : remainders[j] < remainders[i] ? -1 : i - j));
  for (const i of order) {
    if (leftover === 0n) break;
    shares[i] += 1n;
    leftover -= 1n;
  }
  return shares.map((x) => Number(x));
}

export function applyRate(amount: number, rate: string, rounding: Rounding = "HALF_EVEN"): number {
  const { digits, scale } = parseDecimal(rate);
  return toSafeNumber(divRound(BigInt(amount) * digits, 10n ** BigInt(scale), rounding));
}

export function convert(amount: number, fromCurrency: string, toCurrency: string, rate: string, rounding: Rounding = "HALF_EVEN"): number {
  const expFrom = exponent(fromCurrency);
  const expTo = exponent(toCurrency);
  const { digits, scale } = parseDecimal(rate);
  // amount / 10^expFrom * rate * 10^expTo  ==  amount * digits * 10^expTo / (10^expFrom * 10^scale)
  const num = BigInt(amount) * digits * 10n ** BigInt(expTo);
  const den = 10n ** BigInt(expFrom + scale);
  return toSafeNumber(divRound(num, den, rounding));
}
