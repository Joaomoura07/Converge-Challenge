// Controlador da revisão: recalcula as sugestões depois de cada edição e descarta respostas de versões antigas.
// Sem React (testável em Node); o hook useSugestoes só o liga ao componente.

import type { Linha } from "../lista";
import { buscarSugestoes } from "./api";
import { paraItensRevisao, versaoDaLista } from "./aplicar";
import type { DadosRevisao, ItemParaRevisao } from "./tipos";

export type EstadoRevisor = {
  fase: "ocioso" | "carregando" | "pronto" | "erro_rede";
  /** última resposta aceita; pode ser de uma versão anterior da lista (então `desatualizada` é true) */
  dados: DadosRevisao | null;
  versaoDados: string | null;
  /** versão atual da lista, a que a próxima resposta precisa ter */
  versaoAlvo: string | null;
  desatualizada: boolean;
  mensagem: string | null;
};

type Buscar = (itens: ItemParaRevisao[], signal: AbortSignal) => Promise<DadosRevisao>;

export type OpcoesRevisor = {
  buscar?: Buscar;
  /** espera depois da última edição antes de perguntar ao servidor */
  atrasoMs?: number;
};

const vazio: EstadoRevisor = {
  fase: "ocioso", dados: null, versaoDados: null, versaoAlvo: null, desatualizada: false, mensagem: null,
};

export function criarRevisor(opcoes: OpcoesRevisor = {}) {
  const buscar: Buscar = opcoes.buscar ?? ((itens, signal) => buscarSugestoes(itens, { signal }));
  const atraso = opcoes.atrasoMs ?? 700;

  let estado: EstadoRevisor = vazio;
  let linhas: Linha[] = [];
  let sequencia = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let controle: AbortController | null = null;
  let descartadas = 0;
  const ouvintes = new Set<() => void>();

  function mudar(parcial: Partial<EstadoRevisor>) {
    const proximo = { ...estado, ...parcial };
    proximo.desatualizada = proximo.dados !== null && proximo.versaoDados !== proximo.versaoAlvo;
    estado = proximo;
    ouvintes.forEach((f) => f());
  }

  function cancelar() {
    if (timer) clearTimeout(timer);
    timer = null;
    controle?.abort();
    controle = null;
    sequencia += 1; // qualquer resposta em voo passa a ser de uma consulta antiga
  }

  async function disparar() {
    timer = null;
    const versao = versaoDaLista(linhas);
    const itens = paraItensRevisao(linhas);
    const minha = ++sequencia;
    controle?.abort();
    const meu = (controle = new AbortController());
    mudar({ fase: "carregando", mensagem: null });
    try {
      const dados = await buscar(itens, meu.signal);
      if (minha !== sequencia || versao !== estado.versaoAlvo) {
        descartadas += 1; // chegou depois de uma edição ou de uma consulta mais nova
        return;
      }
      mudar({ fase: "pronto", dados, versaoDados: versao, mensagem: null });
    } catch (e) {
      if (minha !== sequencia || meu.signal.aborted) return;
      mudar({ fase: "erro_rede", mensagem: e instanceof Error ? e.message : "Não foi possível revisar a lista." });
    } finally {
      if (controle === meu) controle = null;
    }
  }

  return {
    estado: () => estado,
    assinar(f: () => void) {
      ouvintes.add(f);
      return () => ouvintes.delete(f);
    },
    /** Chamado a cada mudança da lista. Mesma versão = nada a fazer (aceitar/recusar não recalcula). */
    atualizar(novas: Linha[]) {
      linhas = novas;
      const versao = versaoDaLista(novas);
      if (versao === estado.versaoAlvo) return;
      cancelar();
      if (paraItensRevisao(novas).length === 0) {
        mudar({ ...vazio, versaoAlvo: versao });
        return;
      }
      mudar({ versaoAlvo: versao, fase: "carregando", mensagem: null });
      timer = setTimeout(disparar, atraso);
    },
    /** Ação de recuperação do erro de rede: tenta já, sem esperar. */
    repetir() {
      if (paraItensRevisao(linhas).length === 0) return;
      cancelar();
      void disparar();
    },
    /** Para o React: desmontar cancela tudo; remontar (StrictMode) recomeça do zero. */
    parar() {
      cancelar();
      estado = { ...vazio };
    },
    descartadas: () => descartadas,
  };
}

export type Revisor = ReturnType<typeof criarRevisor>;
