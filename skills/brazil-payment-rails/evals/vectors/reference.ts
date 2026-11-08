/**
 * TypeScript reference for the brazil-payment-rails vectors. Same behavior as reference.py:
 * CPF and CNPJ check digits (CNPJ including the alphanumeric format issued from July 2026),
 * boleto barcode and typeable line check digits, and the due-date factor with its 2025-02-22 reset.
 * Dates are ISO strings (YYYY-MM-DD) handled as UTC day counts.
 */

const onlyDigits = (s: string) => s.replace(/\D/g, "");
const onlyAlnum = (s: string) => s.replace(/[^0-9A-Za-z]/g, "").toUpperCase();

// --- CPF ---------------------------------------------------------------------------------------

export function validateCpf(cpf: string): boolean {
  const d = onlyDigits(cpf);
  if (!/^\d{11}$/.test(d) || new Set(d).size === 1) return false;
  const nums = [...d].map(Number);
  for (const n of [9, 10]) {
    let total = 0;
    for (let i = 0; i < n; i++) total += nums[i] * (n + 1 - i);
    const r = total % 11;
    const dv = r < 2 ? 0 : 11 - r;
    if (dv !== nums[n]) return false;
  }
  return true;
}

export function maskCpf(cpf: string): string {
  const d = onlyDigits(cpf);
  if (d.length !== 11) throw new Error("CPF needs 11 digits");
  return `***.${d.slice(3, 6)}.${d.slice(6, 9)}-**`;
}

// --- CNPJ (numeric and alphanumeric) ------------------------------------------------------------

const W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
const W2 = [6, ...W1];

/** Receita Federal rule: the character's ASCII code minus 48 (digits 0-9, letters A=17..Z=42). */
const cnpjValue = (ch: string) => ch.charCodeAt(0) - 48;

export function cnpjCheckDigits(base12: string): string {
  const base = onlyAlnum(base12);
  if (!/^[0-9A-Z]{12}$/.test(base)) throw new Error("CNPJ base needs 12 alphanumeric characters");
  const vals = [...base].map(cnpjValue);
  let r = vals.reduce((s, v, i) => s + v * W1[i], 0) % 11;
  const dv1 = r < 2 ? 0 : 11 - r;
  r = [...vals, dv1].reduce((s, v, i) => s + v * W2[i], 0) % 11;
  const dv2 = r < 2 ? 0 : 11 - r;
  return `${dv1}${dv2}`;
}

export function validateCnpj(cnpj: string): boolean {
  const s = onlyAlnum(cnpj);
  if (!/^[0-9A-Z]{12}[0-9]{2}$/.test(s) || new Set(s).size === 1) return false;
  return s.slice(12) === cnpjCheckDigits(s.slice(0, 12));
}

export function normalizeCnpj(cnpj: string): string {
  const s = onlyAlnum(cnpj);
  if (!validateCnpj(s)) throw new Error("invalid CNPJ");
  return s;
}

export function formatCnpj(cnpj: string): string {
  const s = normalizeCnpj(cnpj);
  return `${s.slice(0, 2)}.${s.slice(2, 5)}.${s.slice(5, 8)}/${s.slice(8, 12)}-${s.slice(12, 14)}`;
}

// --- Boleto: check digits, barcode and typeable line --------------------------------------------

export function mod10(digits: string): number {
  let total = 0;
  let weight = 2;
  for (let i = digits.length - 1; i >= 0; i--) {
    const p = Number(digits[i]) * weight;
    total += p < 10 ? p : p - 9;
    weight = weight === 2 ? 1 : 2;
  }
  return (10 - (total % 10)) % 10;
}

/** General check digit of the 44-digit barcode: weights 2..9 from the right; 0, 10 and 11 become 1. */
export function mod11Barcode(digits43: string): number {
  if (!/^\d{43}$/.test(digits43)) throw new Error("expects the 43 barcode digits without the check digit");
  let total = 0;
  let weight = 2;
  for (let i = digits43.length - 1; i >= 0; i--) {
    total += Number(digits43[i]) * weight;
    weight = weight === 9 ? 2 : weight + 1;
  }
  const dv = 11 - (total % 11);
  return dv === 0 || dv === 10 || dv === 11 ? 1 : dv;
}

export function buildBarcode(bank: string, factor: number, amountMinor: number, freeField: string): string {
  if (!/^\d{3}$/.test(bank)) throw new Error("bank code has 3 digits");
  if (!Number.isInteger(factor) || factor < 1000 || factor > 9999) throw new Error("due-date factor is 1000..9999");
  if (!Number.isInteger(amountMinor) || amountMinor < 0 || amountMinor >= 1e10) throw new Error("amount does not fit 10 digits");
  if (!/^\d{25}$/.test(freeField)) throw new Error("free field has 25 digits");
  const body = `${bank}9${String(factor).padStart(4, "0")}${String(amountMinor).padStart(10, "0")}${freeField}`;
  const dv = mod11Barcode(body);
  return body.slice(0, 4) + String(dv) + body.slice(4);
}

export function validateBarcode(barcode: string): boolean {
  if (!/^\d{44}$/.test(barcode)) return false;
  return Number(barcode[4]) === mod11Barcode(barcode.slice(0, 4) + barcode.slice(5));
}

export function typeableLine(barcode: string): string {
  if (!validateBarcode(barcode)) throw new Error("invalid barcode");
  const f1 = barcode.slice(0, 4) + barcode.slice(19, 24);
  const f2 = barcode.slice(24, 34);
  const f3 = barcode.slice(34, 44);
  const f4 = barcode[4];
  const f5 = barcode.slice(5, 19);
  return `${f1}${mod10(f1)}${f2}${mod10(f2)}${f3}${mod10(f3)}${f4}${f5}`;
}

export function barcodeFromTypeableLine(line: string): string {
  const d = onlyDigits(line);
  if (d.length !== 47) throw new Error("a bank boleto typeable line has 47 digits");
  const f1 = d.slice(0, 10), f2 = d.slice(10, 21), f3 = d.slice(21, 32), f4 = d[32], f5 = d.slice(33, 47);
  for (const field of [f1, f2, f3]) {
    if (mod10(field.slice(0, -1)) !== Number(field.slice(-1))) throw new Error("field check digit does not match");
  }
  const barcode = f1.slice(0, 4) + f4 + f5 + f1.slice(4, 9) + f2.slice(0, 10) + f3.slice(0, 10);
  if (!validateBarcode(barcode)) throw new Error("barcode check digit does not match");
  return barcode;
}

// --- Due-date factor ----------------------------------------------------------------------------

const DAY = 86_400_000;
const toDays = (iso: string) => Math.round(Date.parse(`${iso}T00:00:00Z`) / DAY);
const fromDays = (days: number) => new Date(days * DAY).toISOString().slice(0, 10);

export const BASE_1997 = "1997-10-07";
export const RESET_DATE = "2025-02-22"; // FEBRABAN: factor 1000 means 2025-02-22 from this date on

export function factorFromDueDate(due: string): number {
  const factor = due >= RESET_DATE ? 1000 + (toDays(due) - toDays(RESET_DATE)) : toDays(due) - toDays(BASE_1997);
  if (factor < 1000 || factor > 9999) throw new Error(`${due} is outside the representable range`);
  return factor;
}

/** The factor repeats every 9000 days; pick the cycle closest to a reference date (issue or payment). */
export function dueDateFromFactor(factor: number, reference: string): string {
  if (!Number.isInteger(factor) || factor < 1000 || factor > 9999) throw new Error("due-date factor is 1000..9999");
  const oldDate = toDays(BASE_1997) + factor;
  const newDate = toDays(RESET_DATE) + factor - 1000;
  const ref = toDays(reference);
  return fromDays(Math.abs(oldDate - ref) <= Math.abs(newDate - ref) ? oldDate : newDate);
}
