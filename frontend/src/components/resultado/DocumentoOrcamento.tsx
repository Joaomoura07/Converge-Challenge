"use client";

// Tela 08 do Figma · Documento de orçamento (modal): itens precificados, subtotal e nota. Só os itens com preço entram;
// pendentes e sem preço ficam de fora e a nota diz quantos. Frete em pausa: a nota diz que não está incluído.

import { useEffect, useRef } from "react";
import { reais } from "../orcamento/formato";
import type { ItemLinha, Orcamento } from "@/lib/orcamento/tipos";
import { dataCurta, foraDoSubtotal, linhasDocumento, notaDocumento, subtotal } from "./resultado";

export function DocumentoOrcamento({ orcamento, itens, onFechar }: { orcamento: Orcamento; itens: ItemLinha[]; onFechar: () => void }) {
  const linhas = linhasDocumento(itens);
  const fecharRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    fecharRef.current?.focus();
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && onFechar();
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, [onFechar]);

  return (
    <div className="sh-fundo-modal rs-fundo" onClick={onFechar}>
      <div className="sh-modal rs-documento" role="dialog" aria-modal="true" aria-labelledby="rs-doc-titulo" onClick={(e) => e.stopPropagation()}>
        <p className="sh-etiqueta" style={{ marginTop: 0 }}>
          Documento preliminar · {dataCurta()}
        </p>
        <h2 id="rs-doc-titulo">{orcamento.nome}.</h2>
        <p className="sh-apoio" style={{ marginBottom: 12 }}>
          CEP {orcamento.cep.replace(/^(\d{5})(\d{3})$/, "$1-$2")}
        </p>

        {linhas.length === 0 ? (
          <p className="sh-apoio">Nenhum item com preço ainda. Quando a pesquisa terminar, eles aparecem aqui.</p>
        ) : (
          linhas.map((l) => (
            <div key={l.id} className="linha">
              <span>
                {l.rotulo} · {l.detalhe}
              </span>
              <span>{reais(l.total)}</span>
            </div>
          ))
        )}

        <div className="total">
          <span>Subtotal dos itens precificados</span>
          <strong>{reais(subtotal(linhas))}</strong>
        </div>
        <p className="legal">{notaDocumento(foraDoSubtotal(itens))}</p>

        <div className="rs-acoes">
          <button type="button" className="sh-botao" onClick={() => window.print()}>
            Imprimir / salvar PDF <span aria-hidden="true">↗</span>
          </button>
          <button ref={fecharRef} type="button" className="sh-botao claro" onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
