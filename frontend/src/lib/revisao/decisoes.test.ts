// Aceite e recusa no reducer da lista: cada sugestão vale uma vez e só um clique muda a lista.
import { describe, expect, it } from "vitest";
import { errosPorId, contarErros, estadoInicial, reduzir, type Acao, type EstadoLista, type Linha } from "../lista";
import { complementoParaLinha } from "./aplicar";
import type { ComplementoSugerido, CorrecaoSugerida } from "./tipos";

const rodar = (acoes: Acao[], base: EstadoLista) => acoes.reduce(reduzir, base);
const L = (id: string, descricao: string, quantidade: string, unidade: string): Linha => ({
  id, descricao, quantidade, unidade, categoria: "",
});
const base = (): EstadoLista => ({
  ...estadoInicial,
  linhas: [L("a", "Cimento Votoran", "180", "sc"), L("b", "Porcelanato 90x90", "48", "m2")],
});

const correcao: CorrecaoSugerida = {
  acao: "alterar", remover: [],
  alteracoes: [{ item_id: "a", linha: 1, campo: "unidade", de: "sc", para: "un" }],
};
const comp: ComplementoSugerido = {
  id: "k1", regra: "porcelanato", descricao: "Argamassa colante AC-III 20 kg (saco)", quantidade: 15, unidade: "un",
  categoria: "Revestimentos e argamassas", motivo: "Para 48 m² costumam faltar argamassa.", origem_linhas: [2],
  origem_item_ids: ["b"], estimativa_consumo: true,
};

describe("aceitar correção", () => {
  it("aplica uma vez e registra a decisão", () => {
    const e = rodar([{ tipo: "aceitar_correcao", id: "e1", correcao }], base());
    expect(e.linhas[0].unidade).toBe("un");
    expect(e.decisoes).toEqual({ e1: "aceita" });
    expect(e.tocados["a:unidade"]).toBe(true);
  });

  it("aceite repetido não reaplica (mesmo que a lista tenha voltado ao valor antigo)", () => {
    const uma = rodar([{ tipo: "aceitar_correcao", id: "e1", correcao }], base());
    const editada = reduzir(uma, { tipo: "editar", id: "a", campo: "unidade", valor: "sc" });
    const duas = reduzir(editada, { tipo: "aceitar_correcao", id: "e1", correcao });
    expect(duas).toBe(editada);
    expect(duas.linhas[0].unidade).toBe("sc");
  });

  it("não aplica se a lista mudou desde o cálculo", () => {
    const editada = reduzir(base(), { tipo: "editar", id: "a", campo: "unidade", valor: "kg" });
    const e = reduzir(editada, { tipo: "aceitar_correcao", id: "e1", correcao });
    expect(e).toBe(editada);
    expect(e.decisoes).toEqual({});
  });
});

describe("recusar", () => {
  it("descarta sem alterar a lista e impede um aceite posterior da mesma sugestão", () => {
    const antes = base();
    const e = reduzir(antes, { tipo: "recusar_sugestao", id: "e1" });
    expect(e.linhas).toBe(antes.linhas);
    expect(e.decisoes).toEqual({ e1: "recusada" });
    expect(reduzir(e, { tipo: "aceitar_correcao", id: "e1", correcao })).toBe(e);
  });
});

describe("aceitar complemento", () => {
  it("entra na lista como linha sugerida, uma vez só", () => {
    const acao: Acao = { tipo: "aceitar_complemento", id: "k1", linha: complementoParaLinha(comp, "n1") };
    const uma = reduzir(base(), acao);
    expect(uma.linhas).toHaveLength(3);
    expect(uma.linhas[2].sugerida).toMatchObject({ sugestaoId: "k1", estimativaConsumo: true, origemLinhas: [2] });
    const duas = reduzir(uma, { ...acao, linha: complementoParaLinha(comp, "n2") });
    expect(duas).toBe(uma);
  });

  it("a linha aceita é válida e não desbloqueia nem bloqueia o envio por si", () => {
    const e = reduzir(base(), { tipo: "aceitar_complemento", id: "k1", linha: complementoParaLinha(comp, "n1") });
    const erros = errosPorId(e.linhas);
    expect(erros["n1"]).toBeUndefined();
    expect(contarErros(erros)).toBe(1); // só o "sc" que continua errado: a sugestão não corrigiu nada sozinha
  });

  it("remover o complemento aceito libera a sugestão para ser proposta de novo", () => {
    const e1 = reduzir(base(), { tipo: "aceitar_complemento", id: "k1", linha: complementoParaLinha(comp, "n1") });
    const e2 = reduzir(e1, { tipo: "remover", id: "n1" });
    expect(e2.decisoes).toEqual({});
    expect(e2.linhas).toHaveLength(2);
  });

  it("recusado não vira linha", () => {
    const e1 = reduzir(base(), { tipo: "recusar_sugestao", id: "k1" });
    const e2 = reduzir(e1, { tipo: "aceitar_complemento", id: "k1", linha: complementoParaLinha(comp, "n1") });
    expect(e2).toBe(e1);
    expect(e2.linhas).toHaveLength(2);
  });
});

describe("substituir a lista", () => {
  it("zera as decisões; acrescentar mantém", () => {
    const decidida = reduzir(base(), { tipo: "recusar_sugestao", id: "e1" });
    const nova = [L("z", "Areia média", "10", "m3")];
    expect(reduzir(decidida, { tipo: "importar", linhas: nova, como: "substituir" }).decisoes).toEqual({});
    expect(reduzir(decidida, { tipo: "importar", linhas: nova, como: "acrescentar" }).decisoes).toEqual({ e1: "recusada" });
  });
});
