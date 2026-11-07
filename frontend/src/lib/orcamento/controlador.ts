// Controlador de UM orçamento ao vivo, sem React: assina, lê, reconcilia e limpa. O hook só repassa o estado.
// Fica fora do hook para os testes (eventos repetidos, evento durante a leitura, reconexão, limpeza) rodarem em Node.

import { aplicarEvento, concluirLeitura, estadoVazio, iniciarLeitura, type Estado } from "./armazem";
import { assinar, ler, type ClienteMinimo } from "./conexao";

export type Conexao = "sem-configuracao" | "conectando" | "ao-vivo" | "reconectando" | "erro-leitura";

export type Painel = { estado: Estado; conexao: Conexao; erro: string | null };

/** Quanto esperar o Realtime conectar antes de ler pelo REST mesmo assim. */
export const ESPERA_REALTIME_MS = 4000;

export interface Controlador {
  /** relê as duas tabelas e reconcilia (ação de recuperação) */
  recarregar(): void;
  /** remove a assinatura e descarta leituras em voo */
  parar(): void;
}

export function acompanhar(
  cliente: ClienteMinimo,
  orcamentoId: string,
  aoMudar: (p: Painel) => void,
): Controlador {
  let estado: Estado = estadoVazio();
  let conexao: Conexao = "conectando";
  let erro: string | null = null;
  let ativo = true;
  let geracao = 0;
  let jaConectou = false;
  let espera: ReturnType<typeof setTimeout> | undefined;

  const emitir = () => {
    if (ativo) aoMudar({ estado, conexao, erro });
  };

  const lerEReconciliar = async () => {
    const minha = ++geracao;
    estado = iniciarLeitura(estado);
    try {
      const r = await ler(cliente, orcamentoId);
      if (!ativo || minha !== geracao) return; // desmontou ou já começou uma leitura mais nova
      estado = concluirLeitura(estado, r.orcamento, r.itens);
      erro = null;
      if (conexao === "erro-leitura") conexao = jaConectou ? "ao-vivo" : "reconectando";
    } catch {
      if (!ativo || minha !== geracao) return;
      erro = "Não consegui ler o orçamento. Verifique a conexão e tente de novo.";
      conexao = "erro-leitura";
    }
    emitir();
  };

  const parar = assinar(
    cliente,
    orcamentoId,
    (evento) => {
      if (!ativo) return;
      estado = aplicarEvento(estado, evento);
      emitir();
    },
    (status) => {
      if (!ativo) return;
      if (status === "SUBSCRIBED") {
        if (espera) clearTimeout(espera);
        // Primeira conexão e cada reconexão: lê e reconcilia com o que os eventos trouxeram no meio.
        jaConectou = true;
        conexao = "ao-vivo";
        emitir();
        void lerEReconciliar();
      } else if (jaConectou || status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
        conexao = "reconectando";
        emitir();
      }
    },
  );

  // Se o Realtime não conectar a tempo, lê assim mesmo (REST funciona sem WebSocket) e segue tentando reconectar.
  espera = setTimeout(() => {
    if (!ativo || jaConectou) return;
    conexao = "reconectando";
    emitir();
    void lerEReconciliar();
  }, ESPERA_REALTIME_MS);

  emitir();
  return {
    recarregar: () => void lerEReconciliar(),
    parar: () => {
      ativo = false;
      if (espera) clearTimeout(espera);
      parar();
    },
  };
}
