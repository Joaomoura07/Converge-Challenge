// Revalidação ao editar, respostas atrasadas, erro de rede e C indisponível (sem rede de verdade: busca simulada).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Linha } from "../lista";
import { criarRevisor } from "./revisor";
import type { DadosRevisao, ItemParaRevisao } from "./tipos";

const L = (id: string, descricao: string, quantidade = "1", unidade = "un"): Linha => ({
  id, descricao, quantidade, unidade, categoria: "",
});

const dados = (rotulo: string, extra: Partial<DadosRevisao> = {}): DadosRevisao => ({
  revisao_id: rotulo, erros: [], complementos: [], complementos_disponiveis: true, complementos_erro: null, ...extra,
});

type Pedido = { itens: ItemParaRevisao[]; signal: AbortSignal; resolver: (d: DadosRevisao) => void; rejeitar: (e: Error) => void };

function fabrica() {
  const pedidos: Pedido[] = [];
  const buscar = (itens: ItemParaRevisao[], signal: AbortSignal) =>
    new Promise<DadosRevisao>((resolver, rejeitar) => pedidos.push({ itens, signal, resolver, rejeitar }));
  return { pedidos, revisor: criarRevisor({ buscar, atrasoMs: 100 }) };
}

const esperar = async (ms: number) => {
  await vi.advanceTimersByTimeAsync(ms);
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("revisão automática", () => {
  it("espera a edição assentar e faz uma única consulta", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "T")]);
    revisor.atualizar([L("a", "Ti")]);
    revisor.atualizar([L("a", "Tin")]);
    expect(revisor.estado().fase).toBe("carregando");
    await esperar(99);
    expect(pedidos).toHaveLength(0);
    await esperar(2);
    expect(pedidos).toHaveLength(1);
    expect(pedidos[0].itens[0].descricao).toBe("Tin");
    pedidos[0].resolver(dados("r1"));
    await esperar(0);
    expect(revisor.estado()).toMatchObject({ fase: "pronto", desatualizada: false });
    expect(revisor.estado().dados?.revisao_id).toBe("r1");
  });

  it("mesma lista (aceitar/recusar não mexe nela) não pergunta de novo", async () => {
    const { pedidos, revisor } = fabrica();
    const linhas = [L("a", "Tinta")];
    revisor.atualizar(linhas);
    await esperar(101);
    pedidos[0].resolver(dados("r1"));
    await esperar(0);
    revisor.atualizar([...linhas]);
    await esperar(500);
    expect(pedidos).toHaveLength(1);
  });

  it("lista vazia: nada a revisar, nenhuma consulta", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "   ")]);
    await esperar(500);
    expect(pedidos).toHaveLength(0);
    expect(revisor.estado().fase).toBe("ocioso");
  });
});

describe("retorno atrasado", () => {
  it("resposta de uma versão antiga é descartada e a nova prevalece", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Tinta", "10")]);
    await esperar(101);
    expect(pedidos).toHaveLength(1);

    // o arquiteto edita enquanto a primeira consulta ainda está no ar
    revisor.atualizar([L("a", "Tinta", "20")]);
    expect(pedidos[0].signal.aborted).toBe(true);
    await esperar(101);
    expect(pedidos).toHaveLength(2);

    pedidos[1].resolver(dados("nova"));
    await esperar(0);
    pedidos[0].resolver(dados("velha")); // chega por último, mesmo cancelada
    await esperar(0);

    expect(revisor.estado().dados?.revisao_id).toBe("nova");
    expect(revisor.estado().desatualizada).toBe(false);
    expect(revisor.descartadas()).toBe(1);
  });

  it("resposta velha que chega ANTES da consulta nova também é descartada", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Tinta", "10")]);
    await esperar(101);
    revisor.atualizar([L("a", "Tinta", "20")]);
    pedidos[0].resolver(dados("velha"));
    await esperar(0);
    expect(revisor.estado().dados).toBeNull();
    expect(revisor.estado().fase).toBe("carregando");
    expect(revisor.descartadas()).toBe(1);
  });

  it("editar depois de uma resposta boa marca as sugestões como desatualizadas até a nova chegar", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Tinta", "10")]);
    await esperar(101);
    pedidos[0].resolver(dados("r1"));
    await esperar(0);
    expect(revisor.estado().desatualizada).toBe(false);

    revisor.atualizar([L("a", "Tinta", "11")]);
    expect(revisor.estado().desatualizada).toBe(true);
    expect(revisor.estado().dados?.revisao_id).toBe("r1"); // ainda visível, mas travada na tela
    await esperar(101);
    pedidos[1].resolver(dados("r2"));
    await esperar(0);
    expect(revisor.estado()).toMatchObject({ desatualizada: false });
    expect(revisor.estado().dados?.revisao_id).toBe("r2");
  });
});

describe("falhas", () => {
  it("erro de rede mostra mensagem, guarda a lista e a ação 'tentar de novo' consulta já", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Tinta")]);
    await esperar(101);
    pedidos[0].rejeitar(new Error("Não foi possível falar com o servidor."));
    await esperar(0);
    expect(revisor.estado()).toMatchObject({ fase: "erro_rede", mensagem: "Não foi possível falar com o servidor." });

    revisor.repetir();
    expect(pedidos).toHaveLength(2);
    expect(revisor.estado().fase).toBe("carregando");
    pedidos[1].resolver(dados("ok"));
    await esperar(0);
    expect(revisor.estado()).toMatchObject({ fase: "pronto", mensagem: null });
  });

  it("falha de uma consulta cancelada não vira erro na tela", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Tinta", "1")]);
    await esperar(101);
    revisor.atualizar([L("a", "Tinta", "2")]);
    pedidos[0].rejeitar(new Error("abortado"));
    await esperar(0);
    expect(revisor.estado().fase).toBe("carregando");
    expect(revisor.estado().mensagem).toBeNull();
  });

  it("C indisponível: os erros E1 chegam e o aviso de complementos vem junto", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Cimento Votoran", "180", "sc")]);
    await esperar(101);
    pedidos[0].resolver(dados("r1", {
      complementos_disponiveis: false,
      complementos_erro: "Não foi possível calcular os complementos agora.",
    }));
    await esperar(0);
    const e = revisor.estado();
    expect(e.fase).toBe("pronto");
    expect(e.dados?.complementos_disponiveis).toBe(false);
    expect(e.dados?.complementos_erro).toMatch(/complementos/);
  });

  it("parar() cancela tudo e permite recomeçar (StrictMode)", async () => {
    const { pedidos, revisor } = fabrica();
    revisor.atualizar([L("a", "Tinta")]);
    await esperar(101);
    revisor.parar();
    expect(pedidos[0].signal.aborted).toBe(true);
    pedidos[0].resolver(dados("tarde"));
    await esperar(0);
    expect(revisor.estado().dados).toBeNull();
    revisor.atualizar([L("a", "Tinta")]);
    await esperar(101);
    expect(pedidos).toHaveLength(2);
  });
});
