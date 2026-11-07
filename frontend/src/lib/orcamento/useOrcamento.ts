"use client";

// useOrcamento(id): acompanha `orcamentos` e `orcamento_itens` de UM orçamento por Realtime.
//  - o ID vem da tela (UUID gerado antes do POST /orcamentos): o orçamento pode ainda não existir ("aguardando");
//  - assina primeiro e lê depois; eventos que chegam no meio são preservados (armazem.ts);
//  - ao reconectar, lê de novo e reconcilia;
//  - ao desmontar (ou trocar de id), remove a assinatura e ignora leituras que ainda estavam em voo.
// A lógica fica em controlador.ts (testável sem React); aqui só se liga ao ciclo de vida do componente.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { obterSupabase } from "../supabase";
import { estadoVazio, itensOrdenados } from "./armazem";
import { type ClienteMinimo } from "./conexao";
import { acompanhar, type Conexao, type Controlador, type Painel } from "./controlador";
import type { ItemLinha, Orcamento } from "./tipos";

export type { Conexao } from "./controlador";

export type OrcamentoAoVivo = {
  conexao: Conexao;
  /** false até a primeira leitura terminar */
  carregado: boolean;
  /** null enquanto o POST ainda não gravou o orçamento ("aguardando o envio") */
  orcamento: Orcamento | null;
  /** na ordem da lista do arquiteto (por `linha`) */
  itens: ItemLinha[];
  erro: string | null;
  /** relê as duas tabelas (ação de recuperação depois de um erro de leitura) */
  recarregar: () => void;
};

export function useOrcamento(id: string | null, opcoes?: { cliente?: ClienteMinimo | null }): OrcamentoAoVivo {
  const injetado = opcoes?.cliente;
  const cliente = useMemo<ClienteMinimo | null>(
    () => (injetado !== undefined ? injetado : ((obterSupabase() as unknown as ClienteMinimo | null) ?? null)),
    [injetado],
  );
  const [painel, setPainel] = useState<Painel>({
    estado: estadoVazio(),
    conexao: cliente ? "conectando" : "sem-configuracao",
    erro: null,
  });
  const controlador = useRef<Controlador | null>(null);

  useEffect(() => {
    if (!id || !cliente) {
      setPainel({ estado: estadoVazio(), conexao: cliente ? "conectando" : "sem-configuracao", erro: null });
      return;
    }
    setPainel({ estado: estadoVazio(), conexao: "conectando", erro: null });
    const c = acompanhar(cliente, id, setPainel);
    controlador.current = c;
    return () => {
      c.parar();
      controlador.current = null;
    };
  }, [id, cliente]);

  const itens = useMemo(() => itensOrdenados(painel.estado), [painel.estado]);
  const recarregar = useCallback(() => controlador.current?.recarregar(), []);

  return {
    conexao: painel.conexao,
    carregado: painel.estado.carregado,
    orcamento: painel.estado.orcamento,
    itens,
    erro: painel.erro,
    recarregar,
  };
}
