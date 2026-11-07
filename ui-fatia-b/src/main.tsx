// Prévia dos componentes da fatia B com dados REAIS da pesquisa (src/dados/exemplo-real.json).
// Simula o Supabase Realtime: todos os itens começam "buscando" e chegam um a um.
// ?demo=1 liga o modo projetor.

import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./tokens.css";
import "./components/orcamento/orcamento.css";
import { ItemRow } from "./components/orcamento/ItemRow";
import type { ItemOrcamento } from "./components/orcamento/tipos";
import dados from "./dados/exemplo-real.json";

const ORDEM: Record<string, number> = { definido: 0, buscando: 0, nao_encontrado: 1, erro: 1, pendente_especificacao: 2 };
const reais = dados as unknown as ItemOrcamento[];

function Previa() {
  const [itens, setItens] = useState<ItemOrcamento[]>([]);
  const [rodada, setRodada] = useState(0);
  const demo = new URLSearchParams(location.search).has("demo");

  useEffect(() => {
    setItens(reais.map((i) => ({ id: i.id, descricao: i.descricao, quantidade: i.quantidade, unidade: i.unidade, status: "buscando" })));
    const timers = reais.map((real, n) =>
      setTimeout(() => setItens((atual) => atual.map((i) => (i.id === real.id ? real : i))), 900 + n * 700));
    return () => timers.forEach(clearTimeout);
  }, [rodada]);

  // pendentes juntos no fim (skill, seção 3.3)
  const ordenados = [...itens].sort((a, b) => (ORDEM[a.status] ?? 0) - (ORDEM[b.status] ?? 0));

  return (
    <main className={demo ? "orc-demo" : ""} style={{ maxWidth: 1120, margin: "0 auto", padding: "32px 16px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 600, fontStretch: "125%", margin: 0 }}>Reforma Graças, apto 302</h1>
        <button className="orc-botao" onClick={() => setRodada((r) => r + 1)}>Simular a chegada de novo</button>
      </header>
      <p style={{ color: "var(--cor-texto-2)", margin: "4px 0 24px" }}>
        {itens.filter((i) => i.status !== "buscando").length} de {itens.length} itens pesquisados
      </p>
      <section className="orc-lista" aria-live="polite">
        {ordenados.map((item) => (
          <ItemRow key={item.id} item={item}
                   onResponder={(i, texto) => alert(`repesquisar_item(${i.id}, "${texto}")`)}
                   onPesquisarDeNovo={(i) => alert(`repesquisar_item(${i.id})`)} />
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("raiz")!).render(<StrictMode><Previa /></StrictMode>);
