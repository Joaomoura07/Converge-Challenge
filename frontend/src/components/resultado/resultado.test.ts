import { describe, expect, it } from "vitest";
import type { ItemLinha, Viabilidade } from "@/lib/orcamento/tipos";
import { foraDoSubtotal, linhasDocumento, notaDocumento, resumoParaTela, subtotal, urlExportar, veredito } from "./resultado";

let n = 0;
const item = (p: Partial<ItemLinha>): ItemLinha => ({
  id: `i${++n}`, orcamento_id: "o", linha: n, descricao: `Item ${n}`, status: "definido", atualizado_em: "", ...p,
});
const definido = (descricao: string, qtd: number, emb: string, med: number, extra: Partial<ItemLinha> = {}) =>
  item({ descricao, status: "definido", qtd_embalagens: qtd, embalagem: emb, preco_emb_med: med, ...extra });

describe("linhasDocumento e subtotal", () => {
  it("multiplica embalagens pelo preço médio e soma só os itens precificados", () => {
    const itens = [
      definido("Porcelanato", 30, "caixa 2 m²", 179.8),
      definido("Tinta acrílica", 3, "lata 18 L", 329),
      item({ descricao: "Torneira", status: "pendente_especificacao", pergunta: "Qual modelo?" }),
    ];
    const l = linhasDocumento(itens);
    expect(l.map((x) => [x.rotulo, x.detalhe, x.total])).toEqual([
      ["Porcelanato", "30 caixas 2 m²", 5394],
      ["Tinta acrílica", "3 latas 18 L", 987],
    ]);
    expect(subtotal(l)).toBe(6381);
  });

  it("evita erro de ponto flutuante (0,1 + 0,2)", () => {
    expect(subtotal([{ id: "a", rotulo: "", detalhe: "", total: 0.1 }, { id: "b", rotulo: "", detalhe: "", total: 0.2 }])).toBe(0.3);
  });

  it("usa o nome do produto encontrado quando existe", () => {
    const [l] = linhasDocumento([definido("tinta", 1, "lata", 100, { produto_normalizado: "Suvinil Toque de Seda 18 L" })]);
    expect(l.rotulo).toBe("Suvinil Toque de Seda 18 L");
  });

  it("deixa de fora definido sem quantidade de embalagens (caso real: 'não sei converter m2 em l')", () => {
    const itens = [definido("Coral Decora", 0, "3,6 L", 165), item({ descricao: "Quartzolit", status: "definido", preco_emb_med: 46.9, qtd_embalagens: null })];
    expect(linhasDocumento(itens)).toEqual([]);
    expect(foraDoSubtotal(itens)).toEqual({ pendentes: 0, semPreco: 2, total: 2 });
  });

  it("complemento sugerido só conta se aceito", () => {
    const itens = [
      definido("Selador aceito", 1, "lata", 100, { sugerido: true, aceito: true }),
      definido("Massa recusada", 1, "lata", 900, { sugerido: true, aceito: false }),
      definido("Fita sem decisão", 1, "rolo", 50, { sugerido: true, aceito: null }),
    ];
    expect(linhasDocumento(itens).map((l) => l.rotulo)).toEqual(["Selador aceito"]);
    expect(foraDoSubtotal(itens).total).toBe(0); // recusados nem entram na contagem de "fora"
  });

  it("lista vazia e itens ainda em busca", () => {
    expect(linhasDocumento([])).toEqual([]);
    expect(subtotal([])).toBe(0);
    expect(foraDoSubtotal([item({ status: "buscando" })])).toEqual({ pendentes: 0, semPreco: 1, total: 1 });
  });
});

describe("notaDocumento", () => {
  it("só frete quando tudo está precificado", () => {
    expect(notaDocumento({ pendentes: 0, semPreco: 0, total: 0 })).toMatch(/^Frete não incluído\. Estimativa sujeita/);
  });
  it("singular e plural, como no Figma ('Frete e 1 item pendente não incluídos')", () => {
    expect(notaDocumento({ pendentes: 1, semPreco: 0, total: 1 })).toMatch(/^Frete e 1 item pendente não incluídos\./);
    expect(notaDocumento({ pendentes: 4, semPreco: 2, total: 6 })).toMatch(/^Frete, 4 itens pendentes e 2 itens sem preço não incluídos\./);
  });
  it("não diz que os preços são fictícios (vêm de pesquisa real, com fonte)", () => {
    expect(notaDocumento({ pendentes: 0, semPreco: 0, total: 0 })).not.toMatch(/fictíci/i);
  });
});

describe("veredito", () => {
  const v = (p: Partial<Viabilidade>): Viabilidade => ({ completo: true, cabe: false, cabe_no_minimo: false, ...p });
  it("cabe, só no mínimo, não cabe", () => {
    expect(veredito(v({ cabe: true })).titulo).toBe("Cabe no orçamento");
    expect(veredito(v({ cabe_no_minimo: true })).titulo).toBe("Cabe só no menor preço");
    expect(veredito(v({})).titulo).toBe("Não cabe no orçamento");
  });
  it("nunca afirma 'cabe' com itens sem preço", () => {
    expect(veredito(v({ completo: false, cabe: true }))).toMatchObject({ tom: "talvez", titulo: "Ainda não dá para afirmar" });
  });
  it("status nunca só por cor: sempre tem ícone", () => {
    for (const x of [v({ cabe: true }), v({}), v({ completo: false })]) expect(veredito(x).icone).toBeTruthy();
  });
});

describe("urlExportar", () => {
  it("monta o link do Excel e tolera barra no fim", () => {
    expect(urlExportar("abc", "https://api.exemplo.app/")).toBe("https://api.exemplo.app/orcamentos/abc/exportar.xlsx");
  });
  it("sem NEXT_PUBLIC_API_URL não há link", () => {
    expect(urlExportar("abc", "")).toBeNull();
    expect(urlExportar("abc", undefined)).toBeNull();
  });
  it("escapa o id", () => {
    expect(urlExportar("a b/c", "http://x")).toBe("http://x/orcamentos/a%20b%2Fc/exportar.xlsx");
  });
});

describe("resumoParaTela", () => {
  const base: Viabilidade = { completo: false, cabe: true };
  it("tira a frase repetida do início quando faltam preços", () => {
    expect(resumoParaTela({ ...base, resumo: "Ainda não dá para afirmar: 2 itens ainda sem preço ficaram fora do total." })).toBe("2 itens ainda sem preço ficaram fora do total.");
  });
  it("não mexe em resumo completo nem sem resumo", () => {
    expect(resumoParaTela({ completo: true, cabe: true, resumo: "Cabe: total estimado R$ 10,00." })).toBe("Cabe: total estimado R$ 10,00.");
    expect(resumoParaTela({ completo: false })).toBe("");
  });
});
