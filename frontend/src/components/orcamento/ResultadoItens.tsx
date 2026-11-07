"use client";
// Lista do resultado ao vivo (fatia B): progresso, itens na ordem da skill (pendentes no fim) e os botões
// "Responder" / "Pesquisar de novo" ligados na rota da B. A fatia A só passa os itens que o
// useOrcamento(id) recebe do Supabase Realtime:
//
//     <ResultadoItens itens={itens} />
//
// Os estilos vêm junto (importados aqui): nada a mudar no layout do site.

import "@/styles/papeis-de-cor.css";
import "./orcamento.css";

import { useState } from "react";
import { ItemRow } from "./ItemRow";
import {
  ErroRepesquisa, aplicarResultado, fraseProgresso, ordenarItens, progresso, repesquisarItem,
  type ResultadoApi,
} from "./resultado";
import type { ItemOrcamento } from "./tipos";

interface Props {
  itens: ItemOrcamento[];
  /** Modo projetor (?demo=1): fonte maior e cota mais grossa. */
  demo?: boolean;
  /** Troca a chamada real (útil na prévia e em testes). */
  repesquisar?: (itemId: string, especificacao?: string) => Promise<ResultadoApi>;
}

export function ResultadoItens({ itens, demo, repesquisar = repesquisarItem }: Props) {
  // Enquanto a rota trabalha, o item aparece como "buscando" na hora (o Realtime confirma em seguida).
  const [locais, setLocais] = useState<Record<string, ItemOrcamento>>({});
  const [erros, setErros] = useState<Record<string, string>>({});

  const visiveis = itens.map((i) => locais[i.id] ?? i);
  const p = progresso(visiveis);

  async function pesquisar(item: ItemOrcamento, especificacao?: string) {
    setErros(({ [item.id]: _, ...resto }) => resto);
    const descricao = especificacao ?? item.descricao;
    setLocais((l) => ({ ...l, [item.id]: { id: item.id, descricao, quantidade: item.quantidade, unidade: item.unidade,
                                           status: "buscando" } }));
    try {
      const r = await repesquisar(item.id, especificacao);
      setLocais((l) => ({ ...l, [item.id]: aplicarResultado({ ...item, descricao }, r) }));
    } catch (e) {
      setLocais(({ [item.id]: _, ...resto }) => resto);   // volta a mostrar o item como estava
      setErros((er) => ({ ...er, [item.id]: e instanceof ErroRepesquisa ? e.message : "A pesquisa falhou. Tente de novo." }));
    }
  }

  return (
    <section className={`orc-resultado${demo ? " orc-demo" : ""}`} aria-labelledby="orc-resultado-titulo">
      <div className="orc-resultado__topo">
        <h2 id="orc-resultado-titulo" className="orc-resultado__titulo">Preços pesquisados</h2>
        <p className="orc-resultado__progresso" role="status" aria-live="polite">{fraseProgresso(p)}</p>
      </div>
      {p.total > 0 && (
        <div className="orc-progresso" aria-hidden="true">
          <span className="orc-progresso__feito" style={{ width: `${(p.prontos / p.total) * 100}%` }} />
        </div>
      )}
      <div className="orc-lista">
        {ordenarItens(visiveis).map((item) => (
          <div key={item.id}>
            <ItemRow item={item}
                     onResponder={(i, texto) => pesquisar(i, texto)}
                     onPesquisarDeNovo={(i) => pesquisar(i)} />
            {erros[item.id] && <p className="orc-resultado__erro" role="alert">{erros[item.id]}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}
