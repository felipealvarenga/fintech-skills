/**
 * Test vectors for brazil-payment-rails (TypeScript). Same cases as test_brazil.py.
 *
 * Run against the reference: `npx vitest run skills/brazil-payment-rails`
 * Run against your module:   `BRAZIL_SOLUTION_TS=/abs/path/to/brazil.ts npx vitest run skills/brazil-payment-rails`
 */
import { describe, expect, it } from "vitest";

const modulePath = process.env.BRAZIL_SOLUTION_TS ?? "./reference.ts";
const m = await import(modulePath);

describe("CPF", () => {
  it.each([
    ["529.982.247-25", true], ["52998224725", true], ["529.982.247-26", false], ["111.111.111-11", false],
    ["000.000.000-00", false], ["1234567890", false], ["529.982.247-2A", false],
  ])("validateCpf(%s) = %s", (cpf, valid) => {
    expect(m.validateCpf(cpf)).toBe(valid);
  });

  it("masks all but the middle digits", () => {
    expect(m.maskCpf("529.982.247-25")).toBe("***.982.247-**");
  });
});

describe("CNPJ", () => {
  it("validates the Receita's alphanumeric example 12.ABC.345/01DE-35", () => {
    expect(m.cnpjCheckDigits("12ABC34501DE")).toBe("35");
    expect(m.validateCnpj("12.ABC.345/01DE-35")).toBe(true);
    expect(m.validateCnpj("12.ABC.345/01DE-36")).toBe(false);
  });

  it.each([
    ["11.222.333/0001-81", true], ["11222333000181", true], ["11.222.333/0001-82", false], ["00.000.000/0000-00", false],
    ["11.222.333/0001-8", false], ["12.abc.345/01de-35", true], ["12.ABC.345/01DE-3A", false],
  ])("validateCnpj(%s) = %s", (cnpj, valid) => {
    expect(m.validateCnpj(cnpj)).toBe(valid);
  });

  it("normalizes and formats", () => {
    expect(m.normalizeCnpj("12.abc.345/01de-35")).toBe("12ABC34501DE35");
    expect(m.formatCnpj("12ABC34501DE35")).toBe("12.ABC.345/01DE-35");
    expect(m.formatCnpj("11222333000181")).toBe("11.222.333/0001-81");
    expect(() => m.normalizeCnpj("11.222.333/0001-82")).toThrow();
  });

  it("does not strip letters", () => {
    expect(m.validateCnpj("1234501DE35")).toBe(false);
  });
});

describe("boleto check digits", () => {
  it.each([
    ["1", 8], ["9", 1], ["0", 0], ["12345", 5], ["001905009", 5], ["4014481606", 9], ["0680935031", 4],
  ])("mod10(%s) = %i", (digits, dv) => {
    expect(m.mod10(digits)).toBe(dv);
  });

  it("maps 0, 10 and 11 to 1 in the barcode digit", () => {
    expect(m.mod11Barcode("0".repeat(43))).toBe(1);
    expect(() => m.mod11Barcode("0".repeat(44))).toThrow();
  });

  const SAMPLE_LINE = "00190500954014481606906809350314337370000000100"; // published Banco do Brasil sample, R$ 1,00

  it("validates and round-trips the published sample line", () => {
    const barcode = m.barcodeFromTypeableLine(SAMPLE_LINE);
    expect(barcode).toBe("00193373700000001000500940144816060680935031");
    expect(m.validateBarcode(barcode)).toBe(true);
    expect(barcode[4]).toBe("3");
    expect(m.typeableLine(barcode)).toBe(SAMPLE_LINE);
    expect(Number(barcode.slice(9, 19))).toBe(100);
    expect(m.dueDateFromFactor(Number(barcode.slice(5, 9)), "2008-01-01")).toBe("2007-12-31");
  });

  const sampleBarcode = () => m.buildBarcode("001", m.factorFromDueDate("2026-03-10"), 123456, "1234567890123456789012345");

  it("round-trips a built barcode through the typeable line", () => {
    const barcode = sampleBarcode();
    expect(barcode).toHaveLength(44);
    expect(m.validateBarcode(barcode)).toBe(true);
    const line = m.typeableLine(barcode);
    expect(line).toHaveLength(47);
    expect(m.barcodeFromTypeableLine(line)).toBe(barcode);
    expect(line[32]).toBe(barcode[4]);
    expect(line.slice(33, 47)).toBe(barcode.slice(5, 19));
  });

  it("rejects a tampered digit in any mod-10 field or the check digit", () => {
    const line = m.typeableLine(sampleBarcode());
    for (let pos = 0; pos <= 32; pos++) {
      const bad = line.slice(0, pos) + String((Number(line[pos]) + 1) % 10) + line.slice(pos + 1);
      expect(() => m.barcodeFromTypeableLine(bad)).toThrow();
    }
  });

  it("documents that the mod-11 digit does not catch every change in the fifth field", () => {
    const line = m.typeableLine(sampleBarcode());
    let slipped = 0;
    for (let pos = 33; pos < 47; pos++) {
      for (let delta = 1; delta < 10; delta++) {
        const bad = line.slice(0, pos) + String((Number(line[pos]) + delta) % 10) + line.slice(pos + 1);
        try { m.barcodeFromTypeableLine(bad); slipped++; } catch { /* rejected */ }
      }
    }
    expect(slipped).toBeGreaterThan(0);
    expect(slipped).toBeLessThan(14 * 9);
  });

  it("encodes amount and factor", () => {
    const barcode = sampleBarcode();
    expect(barcode.slice(0, 3)).toBe("001");
    expect(barcode[3]).toBe("9");
    expect(Number(barcode.slice(5, 9))).toBe(m.factorFromDueDate("2026-03-10"));
    expect(Number(barcode.slice(9, 19))).toBe(123456);
  });
});

describe("due-date factor", () => {
  it.each([
    ["2000-07-03", 1000], ["2025-02-21", 9999], ["2025-02-22", 1000], ["2025-03-01", 1007], ["2026-03-10", 1381],
  ])("factorFromDueDate(%s) = %i", (due, factor) => {
    expect(m.factorFromDueDate(due)).toBe(factor);
  });

  it("refuses dates outside the range", () => {
    expect(() => m.factorFromDueDate("1999-01-01")).toThrow();
  });

  it.each([
    [1007, "2025-01-10", "2025-03-01"], [9800, "2024-06-01", "2024-08-06"], [1000, "2025-02-25", "2025-02-22"], [1000, "2000-07-01", "2000-07-03"],
  ])("dueDateFromFactor(%i, %s) = %s", (factor, reference, due) => {
    expect(m.dueDateFromFactor(factor, reference)).toBe(due);
  });

  it("round-trips across the reset", () => {
    for (const d of ["2024-12-31", "2025-02-21", "2025-02-22", "2030-01-01"]) {
      expect(m.dueDateFromFactor(m.factorFromDueDate(d), d)).toBe(d);
    }
  });
});
