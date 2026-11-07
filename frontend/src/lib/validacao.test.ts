import { describe, expect, it } from "vitest";
import {
  formatarCep,
  gerarUuid,
  validarCep,
  validarDescricao,
  validarNomeObra,
  validarQuantidade,
  validarReais,
  validarUnidade,
} from "./validacao";

type R = { ok: true; valor: unknown } | { ok: false; erro: string };
const valor = (r: R) => (r.ok ? r.valor : "ERRO");

describe("CEP", () => {
  it("remove máscara e mantém 8 dígitos como texto", () => {
    expect(valor(validarCep("51020-000"))).toBe("51020000");
    expect(valor(validarCep(" 51.020-000 "))).toBe("51020000");
  });
  it("preserva zero inicial", () => {
    expect(valor(validarCep("01001-000"))).toBe("01001000");
    expect(valor(validarCep("01001000"))).toBe("01001000");
  });
  it("recusa vazio, tamanho errado e letras", () => {
    for (const v of ["", "  ", "1234567", "123456789", "5102A-000", "abc"]) {
      expect(validarCep(v).ok, v).toBe(false);
    }
  });
  it("formata para exibição", () => {
    expect(formatarCep("01001000")).toBe("01001-000");
  });
});

describe("orçamento em reais", () => {
  it.each([
    ["20.000,50", 20000.5],
    ["20000,5", 20000.5],
    ["20000", 20000],
    ["20.000", 20000],
    ["R$ 1.234.567,89", 1234567.89],
    ["0,5", 0.5],
    ["20000.5", 20000.5],
  ])("aceita %s", (texto, esperado) => {
    expect(valor(validarReais(texto))).toBe(esperado);
  });
  it.each(["", "  ", "0", "0,00", "-5", "-20.000,50", "abc", "20mil", "1,2,3", "20.00.000,5", "10,999", "1e5", "Infinity"])(
    "recusa %j",
    (texto) => {
      expect(validarReais(texto).ok).toBe(false);
    },
  );
});

describe("quantidade", () => {
  it("vírgula decimal vira número com ponto", () => {
    expect(valor(validarQuantidade("12,5"))).toBe(12.5);
    expect(valor(validarQuantidade("1.234,50"))).toBe(1234.5);
    expect(valor(validarQuantidade("180"))).toBe(180);
    expect(valor(validarQuantidade("0,25"))).toBe(0.25);
    expect(valor(validarQuantidade("12.5"))).toBe(12.5);
  });
  it("recusa vazio, zero, negativa, texto e ambíguo", () => {
    for (const v of ["", " ", "0", "0,0", "-1", "-0,5", "abc", "12m", "1.234", "NaN", "Infinity", "1,2,3", "1e3"]) {
      expect(validarQuantidade(v).ok, v).toBe(false);
    }
  });
});

describe("unidade", () => {
  it("aceita as oito unidades", () => {
    for (const u of ["m", "m2", "m3", "un", "kg", "l", "cm", "mm"]) expect(valor(validarUnidade(u))).toBe(u);
  });
  it("aceita m² e variações de caixa", () => {
    expect(valor(validarUnidade("m²"))).toBe("m2");
    expect(valor(validarUnidade("M²"))).toBe("m2");
    expect(valor(validarUnidade("m³"))).toBe("m3");
    expect(valor(validarUnidade(" KG "))).toBe("kg");
  });
  it("recusa vazia e desconhecida", () => {
    for (const v of ["", " ", "litro", "m4", "pç"]) expect(validarUnidade(v).ok, v).toBe(false);
  });
});

describe("nome e descrição", () => {
  it("exigem texto e tiram espaços externos", () => {
    expect(valor(validarNomeObra("  Reforma   Apto  "))).toBe("Reforma Apto");
    expect(validarNomeObra("  ").ok).toBe(false);
    expect(validarDescricao("").ok).toBe(false);
    expect(valor(validarDescricao(" tinta  branca "))).toBe("tinta branca");
  });
});

describe("uuid", () => {
  it("gera UUID v4 diferente a cada chamada", () => {
    const a = gerarUuid();
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(gerarUuid()).not.toBe(a);
  });
});
