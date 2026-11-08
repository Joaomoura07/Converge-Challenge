"use client";
// Prévia dos componentes da fatia B no site, com dados REAIS de uma pesquisa (exemplo-real.json).
// Simula o Realtime: todos os itens começam "buscando" e chegam um a um. ?demo=1 liga o modo projetor.
// "Responder" e "Pesquisar de novo" usam uma resposta simulada aqui (os ids da prévia não existem no banco);
// no resultado de verdade, ResultadoItens chama a rota POST /orcamento-itens/{id}/repesquisar.

import { useEffect, useState } from "react";
import { ResultadoItens } from "@/components/orcamento/ResultadoItens";
import { OBJETIVOS, type PedidoRepesquisa, type ResultadoApi } from "@/components/orcamento/resultado";
import type { ItemOrcamento } from "@/components/orcamento/tipos";
import dados from "./exemplo-real.json";

const reais = dados as unknown as ItemOrcamento[];

async function repesquisaSimulada(itemId: string, pedido?: PedidoRepesquisa): Promise<ResultadoApi> {
  await new Promise((r) => setTimeout(r, 1800));
  const base = reais.find((i) => i.status === "definido")!;
  const { id: _id, descricao: _d, quantidade: _q, unidade: _u, ...campos } = base;
  if (typeof pedido === "object" && "aceitarMedia" in pedido) {   // "Usar a média": o pendente vira estimativa definida
    const proprio = reais.find((i) => i.id === itemId) ?? base;   // no real, o item continua sendo ele mesmo
    const { id: _pid, descricao: _pd, quantidade: _pq, unidade: _pu, ...dele } = proprio;
    return { ...dele, item_id: itemId, status: "definido", pergunta: null, estimativa: true,
             motivo: "Sem marca nem modelo: o preço é a média de produtos parecidos, aceita por você (simulação)." };
  }
  if (typeof pedido === "object") {   // alternativa simulada: no real, a IA sugere e as lojas confirmam o preço
    const rotulo = OBJETIVOS.find((o) => o.objetivo === pedido.objetivo)!.rotulo.toLowerCase();
    return { ...campos, item_id: itemId, produto_normalizado: `${base.produto_normalizado} (simulação: ${rotulo})`,
             motivo: `Alternativa simulada: ${rotulo}. No resultado real, a IA sugere o produto e as lojas confirmam o preço.`,
             iteracoes: 1 };
  }
  return { ...campos, item_id: itemId, produto_normalizado: pedido ?? base.produto_normalizado, iteracoes: 1 };
}

export default function PreviaB() {
  const [itens, setItens] = useState<ItemOrcamento[]>([]);
  const [rodada, setRodada] = useState(0);
  const [demo, setDemo] = useState(false);

  useEffect(() => setDemo(new URLSearchParams(window.location.search).has("demo")), []);

  useEffect(() => {
    setItens(reais.map((i) => ({ id: i.id, descricao: i.descricao, quantidade: i.quantidade, unidade: i.unidade,
                                 status: "buscando" })));
    const timers = reais.map((real, n) =>
      setTimeout(() => setItens((atual) => atual.map((i) => (i.id === real.id ? real : i))), 900 + n * 700));
    return () => timers.forEach(clearTimeout);
  }, [rodada]);

  return (
    <main className="pagina">
      <header className="topo">
        <p className="marca">OrçaAI</p>
        <p className="lema">Prévia dos preços</p>
      </header>
      <p>
        <button type="button" className="botao-secundario" onClick={() => setRodada((r) => r + 1)}>
          Simular a chegada de novo
        </button>
      </p>
      <ResultadoItens itens={itens} demo={demo} repesquisar={repesquisaSimulada} />
    </main>
  );
}
