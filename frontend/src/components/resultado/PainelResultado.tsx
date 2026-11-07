"use client";

// Resultado da Fatia C no site: subtotal, "cabe ou não", onde comprar, ganho de tempo e Exportar.
// Referência: Figma, tela 08 (cabeçalho "Subtotal estimado" + "Prévia do documento"). Estilos: classes `sh-*` do site + `rs-*`.
// Os dados vêm do hook useOrcamento (orcamento.logistica / viabilidade / ganho); aqui só se desenha.

import { useState } from "react";
import { reais } from "../orcamento/formato";
import type { ItemLinha, Orcamento } from "@/lib/orcamento/tipos";
import { DocumentoOrcamento } from "./DocumentoOrcamento";
import { faixa, foraDoSubtotal, linhasDocumento, resumoParaTela, subtotal, urlExportar, veredito } from "./resultado";
import "./resultado.css";

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

export function PainelResultado({ orcamento, itens }: { orcamento: Orcamento; itens: ItemLinha[] }) {
  const [documento, setDocumento] = useState(false);
  const { viabilidade, logistica, ganho } = orcamento;
  const linhas = linhasDocumento(itens);
  const fora = foraDoSubtotal(itens);
  const excel = urlExportar(orcamento.id);
  const ver = viabilidade ? veredito(viabilidade) : null;

  return (
    <div className="rs-painel">
      <div className="rs-topo">
        <div>
          <p className="sh-etiqueta" style={{ margin: 0 }}>
            Subtotal estimado
          </p>
          <span className="rs-valor">{reais(subtotal(linhas))}</span>
          <p className="sh-apoio" style={{ margin: "2px 0 0" }}>
            {plural(linhas.length, "material", "materiais")} · frete ainda não incluído
            {fora.total > 0 && ` · ${plural(fora.total, "item fora", "itens fora")} do subtotal`}
          </p>
        </div>
        <div className="rs-botoes">
          <button type="button" className="sh-botao" onClick={() => setDocumento(true)}>
            Prévia do documento <span aria-hidden="true">↗</span>
          </button>
          {excel ? (
            <a className="sh-botao claro" href={excel} download="plano-de-compra.xlsx">
              Baixar plano em Excel
            </a>
          ) : (
            <span className="sh-botao claro" aria-disabled="true" title="Defina NEXT_PUBLIC_API_URL para baixar o Excel">
              Baixar plano em Excel
            </span>
          )}
        </div>
      </div>

      {viabilidade && ver && (
        <section className="rs-bloco" aria-labelledby="rs-cabe">
          <p className="sh-etiqueta" id="rs-cabe" style={{ margin: 0 }}>
            Orçamento do cliente · {reais(viabilidade.orcamento_cliente ?? orcamento.orcamento_cliente)}
          </p>
          <p className={`rs-veredito rs-${ver.tom}`}>
            <span aria-hidden="true">{ver.icone}</span> <span>{ver.titulo}</span>
          </p>
          {viabilidade.resumo && <p className="rs-texto">{resumoParaTela(viabilidade)}</p>}
          {faixa(viabilidade) && <p className="sh-apoio">Faixa com estimativas: {faixa(viabilidade)}</p>}
          {viabilidade.sugestoes && viabilidade.sugestoes.length > 0 && !viabilidade.cabe && (
            <>
              <p className="sh-etiqueta">Onde economizar</p>
              <ul className="rs-lista">
                {viabilidade.sugestoes.slice(0, 3).map((s, i) => (
                  <li key={`${s.tipo}-${i}`}>{s.texto}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {logistica?.lojas && logistica.lojas.length > 0 && (
        <section className="rs-bloco" aria-labelledby="rs-onde">
          <p className="sh-etiqueta" id="rs-onde" style={{ margin: 0 }}>
            Onde comprar · menor preço por item
          </p>
          <ul className="rs-lojas">
            {logistica.lojas.map((l) => (
              <li key={l.id}>
                <span>
                  {l.nome}
                  <small>{plural(l.itens.length, "item", "itens")}</small>
                </span>
                <strong>{reais(l.subtotal)}</strong>
              </li>
            ))}
          </ul>
          {!!logistica.frete_total && <p className="sh-apoio">Frete: {reais(logistica.frete_total)}</p>}
        </section>
      )}

      {ganho?.resumo && (
        <section className="rs-bloco" aria-labelledby="rs-ganho">
          <p className="sh-etiqueta" id="rs-ganho" style={{ margin: 0 }}>
            Ganho de tempo
          </p>
          <p className="rs-texto rs-ganho">{ganho.resumo}</p>
        </section>
      )}

      {documento && <DocumentoOrcamento orcamento={orcamento} itens={itens} onFechar={() => setDocumento(false)} />}
    </div>
  );
}
