import { describe, expect, it } from "vitest";
import type { ItemLinha, Viabilidade } from "@/lib/orcamento/tipos";
import { contagem, foraDoSubtotal, itemParaTela, itensParaTela, linhasDocumento, linkRaciocinio, mesAno, notaDocumento, resumoParaTela, subtotal, tituloEditorial, urlExportar, veredito } from "./resultado";

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
  it("tudo precificado: só o aviso, sem citar frete (em pausa na demo)", () => {
    expect(notaDocumento({ pendentes: 0, semPreco: 0, total: 0 })).toMatch(/^Estimativa sujeita/);
    expect(notaDocumento({ pendentes: 4, semPreco: 2, total: 6 })).not.toMatch(/frete/i);
  });
  it("singular e plural ('1 item pendente não incluído')", () => {
    expect(notaDocumento({ pendentes: 1, semPreco: 0, total: 1 })).toMatch(/^1 item pendente não incluído\./);
    expect(notaDocumento({ pendentes: 3, semPreco: 0, total: 3 })).toMatch(/^3 itens pendentes não incluídos\./);
    expect(notaDocumento({ pendentes: 4, semPreco: 2, total: 6 })).toMatch(/^4 itens pendentes e 2 itens sem preço não incluídos\./);
  });
  it("não diz que os preços são fictícios (vêm de pesquisa real, com fonte)", () => {
    expect(notaDocumento({ pendentes: 0, semPreco: 0, total: 0 })).not.toMatch(/fictíci/i);
  });
});

describe("veredito", () => {
  const v = (p: Partial<Viabilidade>): Viabilidade => ({ completo: true, cabe: false, cabe_no_minimo: false, ...p });
  it("cabe, só no mínimo, não cabe", () => {
    expect(veredito(v({ cabe: true }))).toMatchObject({ tom: "sim", titulo: "Dentro do orçamento" });
    expect(veredito(v({ cabe_no_minimo: true })).titulo).toBe("Cabe só no menor preço");
    expect(veredito(v({})).titulo).toBe("Não cabe no orçamento");
  });
  it("com itens sem preço que já cabem: verde, 'Dentro do orçamento' e a ressalva 'até agora'", () => {
    expect(veredito(v({ completo: false, cabe: true, itens_sem_preco: [1, 4] })))
      .toMatchObject({ tom: "sim", icone: "✓", titulo: "Dentro do orçamento", nota: "Até agora: 2 itens sem preço ficaram fora da conta." });
    expect(veredito(v({ completo: false, cabe: true, itens_sem_preco: [3] })).nota).toBe("Até agora: 1 item sem preço ficou fora da conta.");
    expect(veredito(v({ completo: false, cabe: true })).nota).toMatch(/^Até agora: há itens sem preço/);
  });
  it("item sem preço só aumenta a conta: se nem o menor preço cabe, já não cabe", () => {
    expect(veredito(v({ completo: false, cabe: false, cabe_no_minimo: false, itens_sem_preco: [0] })))
      .toMatchObject({ tom: "nao", titulo: "Não cabe no orçamento", nota: "1 item sem preço ficou fora da conta; a diferença tende a ser maior." });
  });
  it("com itens sem preço e só o menor preço cabendo, ou sem os dados, continua incerto", () => {
    expect(veredito(v({ completo: false, cabe: false, cabe_no_minimo: true }))).toMatchObject({ tom: "talvez", titulo: "Ainda não dá para afirmar" });
    expect(veredito({ completo: false })).toMatchObject({ tom: "talvez", titulo: "Ainda não dá para afirmar" });
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

const sp = (t: string) => t.replace(/\u00a0/g, " "); // o formatador de moeda usa espaço não separável

describe("itemParaTela e itensParaTela", () => {
  const fonte = (loja: string, p: number) => ({ loja, dominio: `${loja.toLowerCase()}.com.br`, url: `https://${loja.toLowerCase()}.com.br/p`, preco_embalagem: p });
  const porcelanato = () =>
    definido("Porcelanato 90x90", 33, "caixa 1,62 m²", 118.9, {
      categoria: "Revestimentos", quantidade: 53.46, unidade: "m2", produto_normalizado: "Portobello Cimento 90x90",
      preco_un_med: 73.4, unidade_preco: "m2", imagem_url: "https://img.exemplo/p.jpg", preco_data: "2026-11-06T09:41:00Z",
      fontes: [fonte("Leroy", 118.9), fonte("Telhanorte", 112.5)],
    });

  it("monta a linha como o Figma: nome, loja de menor preço · categoria, quantidade, total e preço por unidade", () => {
    const t = itemParaTela(porcelanato());
    expect(t).toMatchObject({
      nome: "Portobello Cimento 90x90", detalhe: "Porcelanato 90x90", loja: "Telhanorte · Revestimentos",
      quantidade: "53,46 m²", compra: "33 caixas 1,62 m²", total: 3923.7, unitario: expect.stringMatching(/R\$.73,40 \/ m²/),
      situacao: "precificado", imagem: "https://img.exemplo/p.jpg",
    });
    expect(t.fontes.map((f) => f.loja)).toEqual(["Telhanorte", "Leroy"]); // mais barata primeiro
    expect(sp(t.fontes[0].preco)).toBe("R$ 112,50 / caixa 1,62 m²");
  });

  it("sem preço por unidade, mostra o preço da embalagem", () => {
    expect(sp(itemParaTela(definido("Tinta", 2, "lata 18 L", 499)).unitario)).toBe("R$ 499,00 / lata 18 L");
  });

  it("pendente mostra a pergunta; não encontrado mostra o motivo; buscando avisa", () => {
    expect(itemParaTela(item({ status: "pendente_especificacao", pergunta: "Qual acabamento?" }))).toMatchObject({ situacao: "pendente", aviso: "Qual acabamento?", total: null, unitario: "" });
    expect(itemParaTela(item({ status: "nao_encontrado", motivo: "sem resultado" }))).toMatchObject({ situacao: "sem-preco", aviso: "sem resultado", total: null });
    expect(itemParaTela(item({ status: "buscando" }))).toMatchObject({ situacao: "buscando", aviso: "Buscando…" });
  });

  it("definido sem qtd_embalagens não vira número (caso real: 'não sei converter m2 em l')", () => {
    const t = itemParaTela(item({ status: "definido", preco_emb_med: 165, qtd_embalagens: null }));
    expect(t.total).toBeNull();
    expect(t.situacao).toBe("sem-preco");
  });

  it("só aceita imagem e link http(s)", () => {
    const t = itemParaTela(definido("X", 1, "un", 10, { imagem_url: "javascript:alert(1)", fontes: [{ ...fonte("A", 10), url: "javascript:alert(1)" }] }));
    expect(t.imagem).toBeNull();
    expect(t.fontes[0].url).toBeNull();
  });

  it("pendentes e sem preço vão para o fim; complemento recusado some", () => {
    const lista = itensParaTela([
      item({ descricao: "Pendente", status: "pendente_especificacao", pergunta: "?" }),
      definido("Tinta", 1, "lata", 100),
      item({ descricao: "Não achei", status: "nao_encontrado" }),
      definido("Recusado", 1, "lata", 900, { sugerido: true, aceito: false }),
      definido("Rejunte", 1, "saco", 50),
    ]);
    expect(lista.map((t) => t.nome)).toEqual(["Tinta", "Rejunte", "Não achei", "Pendente"]);
  });
});

describe("textos editoriais", () => {
  it("contagem com dois dígitos, singular e plural", () => {
    expect(contagem(3, "item precificado", "itens precificados")).toBe("03 itens precificados");
    expect(contagem(1, "item pendente", "itens pendentes")).toBe("01 item pendente");
    expect(contagem(0, "item pendente", "itens pendentes")).toBe("00 itens pendentes");
  });
  it("título: última palavra em itálico com ponto", () => {
    expect(tituloEditorial("Residência Aurora")).toEqual({ titulo: "Residência", destaque: "Aurora." });
    expect(tituloEditorial("Cozinha Planejada — Graças")).toEqual({ titulo: "Cozinha Planejada —", destaque: "Graças." });
    expect(tituloEditorial("Casa")).toEqual({ titulo: "", destaque: "Casa." });
    expect(tituloEditorial("Casa.")).toEqual({ titulo: "", destaque: "Casa." });
  });
  it("mês e ano em português", () => {
    expect(mesAno("2026-11-07T10:00:00Z")).toBe("novembro de 2026");
  });
});

describe("linkRaciocinio (trace público do Langfuse)", () => {
  it("devolve o link quando é http(s)", () => {
    expect(linkRaciocinio("https://us.cloud.langfuse.com/project/p1/traces/abc")).toBe(
      "https://us.cloud.langfuse.com/project/p1/traces/abc",
    );
  });
  it("esconde o link quando vem vazio (Langfuse fora ou orçamento antigo)", () => {
    expect(linkRaciocinio(null)).toBeNull();
    expect(linkRaciocinio(undefined)).toBeNull();
    expect(linkRaciocinio("")).toBeNull();
  });
  it("recusa protocolo perigoso e texto que não é endereço", () => {
    expect(linkRaciocinio("javascript:alert(1)")).toBeNull();
    expect(linkRaciocinio("data:text/html,oi")).toBeNull();
    expect(linkRaciocinio("não é um link")).toBeNull();
  });
});

describe("fonte mostra o preço do anúncio", () => {
  it("usa preco_anunciado e a embalagem do anúncio (o mesmo que aparece ao clicar no link)", () => {
    const fonte = { loja: "Armazemcoral", dominio: "armazemcoral.com.br", url: "https://armazemcoral.com.br/selador",
      preco_embalagem: 349.5, embalagem: "lata 18 L", preco_anunciado: 69.9, embalagem_anunciada: "galão 3,6 L" };
    const tela = itemParaTela({ id: "s", descricao: "Selador Coral", status: "definido", qtd_embalagens: 1, embalagem: "lata 18 L",
      preco_emb_min: 239.9, preco_emb_med: 294.7, preco_emb_max: 349.5, fontes: [fonte] } as never);
    expect(tela.fontes[0].preco.replace(/\s/g, " ")).toBe("R$ 69,90 / galão 3,6 L");
  });
  it("item antigo, sem preco_anunciado, continua mostrando o convertido", () => {
    const fonte = { loja: "Telhanorte", dominio: "telhanorte.com.br", url: "https://t/s", preco_embalagem: 239.9, embalagem: "lata 18 L" };
    const tela = itemParaTela({ id: "s", descricao: "Selador", status: "definido", qtd_embalagens: 1, embalagem: "lata 18 L",
      preco_emb_min: 239.9, preco_emb_med: 239.9, preco_emb_max: 239.9, fontes: [fonte] } as never);
    expect(tela.fontes[0].preco.replace(/\s/g, " ")).toBe("R$ 239,90 / lata 18 L");
  });
});
