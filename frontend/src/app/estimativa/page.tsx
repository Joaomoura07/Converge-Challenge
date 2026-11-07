"use client";

import { useEffect, useState } from "react";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import { ITENS_ESTIMATIVA, SUBTOTAL, reais } from "@/lib/prototipo";

// Telas 05, 06 e 08 · Estimativa (materiais), Fontes e fornecedores, Documento de orçamento (modal)
export default function Estimativa() {
  const [aba, setAba] = useState<"materiais" | "fontes">("materiais");
  const [selecionado, setSelecionado] = useState(ITENS_ESTIMATIVA[0].id);
  const [documento, setDocumento] = useState(false);

  useEffect(() => {
    if (!documento) return;
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && setDocumento(false);
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, [documento]);

  const item = ITENS_ESTIMATIVA.find((i) => i.id === selecionado)!;
  const definidos = ITENS_ESTIMATIVA.filter((i) => !i.pendente);
  const pendentes = ITENS_ESTIMATIVA.length - definidos.length;

  return (
    <>
      <CabecalhoPagina
        trilha={[{ rotulo: "Estimativas", href: "/" }, { rotulo: "Residência Aurora" }, { rotulo: "Atual" }]}
        etiqueta="Caderno de materiais · novembro 2026"
        titulo="Residência"
        destaque="Aurora."
        apoio="Clara & Miguel · Recife, PE · Revisão 01"
        acao={
          <div className="sh-subtotal">
            <p className="sh-etiqueta" style={{ margin: 0 }}>
              Subtotal estimado
            </p>
            <span className="valor">{reais.format(SUBTOTAL)}</span>
            <p className="sh-apoio" style={{ fontSize: 10, marginBottom: 8 }}>
              Estimativas · fonte indicada em cada item
            </p>
            <button type="button" className="sh-botao" onClick={() => setDocumento(true)}>
              Prévia do documento <span aria-hidden="true">↗</span>
            </button>
          </div>
        }
      />

      <p className="sh-resumo">
        <span className="ok">{String(definidos.length).padStart(2, "0")} itens especificados</span>
        <span className="pend">{String(pendentes).padStart(2, "0")} sem pendente</span>
        <span>Preço a confirmar</span>
      </p>

      <div className="sh-duas">
        <div>
          <div className="sh-abas" role="tablist" aria-label="Seções da estimativa">
            <button type="button" role="tab" className="sh-aba" aria-selected={aba === "materiais"} onClick={() => setAba("materiais")}>
              Materiais · {String(ITENS_ESTIMATIVA.length).padStart(2, "0")}
            </button>
            <button type="button" role="tab" className="sh-aba" aria-selected={aba === "fontes"} onClick={() => setAba("fontes")}>
              Fontes · {String(definidos.length).padStart(2, "0")}
            </button>
          </div>

          {aba === "materiais" ? (
            <div role="tabpanel">
              {ITENS_ESTIMATIVA.map((i) => (
                <button key={i.id} type="button" className="sh-item" aria-pressed={selecionado === i.id} onClick={() => setSelecionado(i.id)}>
                  <span className="foto" aria-hidden="true">
                    {i.pendente ? "?" : ""}
                  </span>
                  <span>
                    <span className={`nome${selecionado === i.id ? " sel" : ""}`}>{i.nome}</span>
                    <small>{i.detalhe}</small>
                    <small>{i.loja}</small>
                  </span>
                  <span className="qtd-col" style={{ fontSize: 12 }}>
                    {i.quantidade}
                  </span>
                  <span className="preco">
                    {i.total === null ? (
                      <span className="sh-aviso" style={{ fontWeight: 400, fontSize: 11 }}>
                        Revisar especificação ↗
                      </span>
                    ) : (
                      <>
                        {reais.format(i.total)}
                        <small>{i.unitario}</small>
                      </>
                    )}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div role="tabpanel">
              {definidos.flatMap((i) =>
                i.fontes.map((f) => (
                  <div key={`${i.id}-${f.dominio}`} className="sh-fonte">
                    <span>
                      {f.loja}
                      <small style={{ display: "block" }}>
                        {i.nome} · {f.dominio}
                      </small>
                    </span>
                    <strong style={{ fontSize: 13 }}>{f.preco}</strong>
                  </div>
                )),
              )}
            </div>
          )}
        </div>

        <aside className="sh-lateral sh-ref" aria-label="Referência selecionada">
          <p className="sh-etiqueta" style={{ marginTop: 0 }}>
            Referência selecionada
          </p>
          <div className="imagem" aria-hidden="true" />
          <h3>{item.nome}</h3>
          <p className="sh-apoio">{item.loja}</p>
          {item.pendente ? (
            <p className="sh-aviso" style={{ fontSize: 13 }}>
              Sem preço: complete modelo e acabamento.
            </p>
          ) : (
            <p style={{ fontSize: 20, margin: "8px 0 0" }}>{item.unitario}</p>
          )}
          <dl>
            <dt>Unidade da oferta</dt>
            <dd>{item.quantidade}</dd>
            <dt>Fontes e fornecedores</dt>
            <dd>{item.fontes.length ? item.fontes.map((f) => f.dominio).join(", ") : "A confirmar com o fornecedor"}</dd>
          </dl>
        </aside>
      </div>

      {documento && (
        <div className="sh-fundo-modal" onClick={() => setDocumento(false)}>
          <div className="sh-modal" role="dialog" aria-modal="true" aria-labelledby="doc-titulo" onClick={(e) => e.stopPropagation()}>
            <p className="sh-etiqueta" style={{ marginTop: 0 }}>
              Documento preliminar · 07/11/2026
            </p>
            <h2 id="doc-titulo">Residência Aurora.</h2>
            <p className="sh-apoio" style={{ marginBottom: 12 }}>
              Clara &amp; Miguel · Recife, PE
            </p>
            {definidos.map((i) => (
              <div key={i.id} className="linha">
                <span>
                  {i.nome} · {i.quantidade}
                </span>
                <span>{reais.format(i.total ?? 0)}</span>
              </div>
            ))}
            <div className="total">
              <span>Subtotal dos itens especificados</span>
              <strong>{reais.format(SUBTOTAL)}</strong>
            </div>
            <p className="legal">Preços e disponibilidade a confirmar com os fornecedores. Itens pendentes ficam fora do subtotal. Dados fictícios de demonstração.</p>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="button" className="sh-botao" onClick={() => window.print()}>
                Imprimir / salvar PDF
              </button>
              <button type="button" className="sh-botao claro" onClick={() => setDocumento(false)} autoFocus>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
