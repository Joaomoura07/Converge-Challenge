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
import { reais } from "./formato";
import {
  ErroRepesquisa, aplicarResultado, fraseProgresso, ordenarItens, progresso, repesquisarItem,
  type PedidoRepesquisa, type ResultadoApi, type TrocaAlternativa,
} from "./resultado";
import type { ItemOrcamento } from "./tipos";

interface Props {
  itens: ItemOrcamento[];
  /** Modo projetor (?demo=1): fonte maior e cota mais grossa. */
  demo?: boolean;
  /** Troca a chamada real (útil na prévia e em testes). */
  repesquisar?: (itemId: string, pedido?: PedidoRepesquisa) => Promise<ResultadoApi>;
}

export function ResultadoItens({ itens, demo, repesquisar = repesquisarItem }: Props) {
  // Enquanto a rota trabalha, o item aparece como "buscando" na hora (o Realtime confirma em seguida).
  const [locais, setLocais] = useState<Record<string, ItemOrcamento>>({});
  const [erros, setErros] = useState<Record<string, string>>({});
  // Depois de uma alternativa que trocou o produto: o que havia antes, para o arquiteto escolher com qual fica.
  const [trocas, setTrocas] = useState<Record<string, TrocaAlternativa["antes"]>>({});

  const visiveis = itens.map((i) => locais[i.id] ?? i);
  const p = progresso(visiveis);

  async function pesquisar(item: ItemOrcamento, pedido?: PedidoRepesquisa) {
    setErros(({ [item.id]: _, ...resto }) => resto);
    setTrocas(({ [item.id]: _, ...resto }) => resto);
    // Resposta à pergunta ou "voltar para o anterior": o título passa a ser esse texto.
    let descricao = typeof pedido === "string" ? pedido
      : typeof pedido === "object" && "voltarPara" in pedido ? pedido.voltarPara : item.descricao;
    setLocais((l) => ({ ...l, [item.id]: { id: item.id, descricao, quantidade: item.quantidade, unidade: item.unidade,
                                           status: "buscando" } }));
    try {
      const r = await repesquisar(item.id, pedido);
      if (r.alternativa?.trocou && r.alternativa.agora) {
        // a alternativa valeu: o título vira o produto sugerido e a tela oferece voltar ao anterior
        descricao = r.alternativa.agora;
        const antes = r.alternativa.antes;
        setTrocas((t) => ({ ...t, [item.id]: antes }));
      }
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
                     onPesquisarDeNovo={(i) => pesquisar(i)}
                     onPesquisarAlternativa={(i, objetivo) => pesquisar(i, { objetivo })}
                     onAceitarMedia={(i) => pesquisar(i, { aceitarMedia: true })} />
            {trocas[item.id] && item.status !== "buscando" && (
              <div className="orc-item__pergunta" role="status">
                <p>
                  Antes: <strong>{trocas[item.id].descricao}</strong>
                  {trocas[item.id].preco_emb_med != null && <> · {reais(trocas[item.id].preco_emb_med as number)}
                    {trocas[item.id].embalagem ? ` por ${trocas[item.id].embalagem}` : ""}</>}
                </p>
                <p>
                  Agora: <strong>{item.produto_normalizado || item.descricao}</strong>
                  {item.preco_emb_med != null && <> · {reais(item.preco_emb_med)}{item.embalagem ? ` por ${item.embalagem}` : ""}</>}
                </p>
                <div className="orc-item__acoes">
                  <button type="button" className="orc-botao orc-botao--principal"
                          onClick={() => setTrocas(({ [item.id]: _, ...resto }) => resto)}>
                    Ficar com o novo
                  </button>
                  <button type="button" className="orc-botao"
                          onClick={() => pesquisar(item, { voltarPara: trocas[item.id].descricao })}>
                    Voltar para o anterior
                  </button>
                </div>
              </div>
            )}
            {erros[item.id] && <p className="orc-resultado__erro" role="alert">{erros[item.id]}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}
