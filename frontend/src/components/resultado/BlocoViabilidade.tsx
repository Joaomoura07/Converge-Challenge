"use client";

// "Cabe no orçamento?", onde comprar (menor preço por item) e ganho de tempo. Só desenha o que a API já calculou
// (orcamento.viabilidade / logistica / ganho). Estilos: classes `sh-*` do site + `rs-*`.

import { reais } from "../orcamento/formato";
import type { Orcamento } from "@/lib/orcamento/tipos";
import { faixa, resumoParaTela, veredito } from "./resultado";
import "./resultado.css";

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

export function BlocoViabilidade({ orcamento }: { orcamento: Orcamento }) {
  const { viabilidade, logistica, ganho } = orcamento;
  const ver = viabilidade ? veredito(viabilidade) : null;
  return (
    <>
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
                  <small>
                    {[
                      plural(l.itens.length, "item", "itens"),
                      l.tempo_min != null && l.tempo_min > 0 && l.distancia_km != null && l.distancia_km > 0
                        ? `${l.distancia_km.toFixed(1).replace(".", ",")} km`
                        : null,
                      l.tempo_min != null && l.tempo_min > 0 ? `${l.tempo_min} min` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
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
    </>
  );
}
