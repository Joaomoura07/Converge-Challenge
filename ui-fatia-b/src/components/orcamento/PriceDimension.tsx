"use client";
// A "cota de preço": a faixa mín–médio–máx desenhada como linha de cota de desenho técnico
// (linhas de chamada nas pontas, marcas oblíquas a 45° e o valor médio escrito sobre a linha).
// Carregando = linha tracejada ("linha oculta": ainda não definido). Ver skills/04-ui-design.md, seções 1 e 4.

import { reais, reaisCurto } from "./formato";

interface Props {
  min?: number | null;
  med?: number | null;
  max?: number | null;
  carregando?: boolean;
  /** true quando o dado acabou de chegar: a linha se fecha da esquerda para a direita (300 ms). */
  chegou?: boolean;
  rotulo?: string; // ex.: "por lata 18 L"
}

export function PriceDimension({ min, med, max, carregando, chegou, rotulo }: Props) {
  const temPreco = !carregando && min != null && med != null && max != null;
  const faixa = temPreco ? max! - min! : 0;
  const posicao = temPreco && faixa > 0 ? (med! - min!) / faixa : 0.5; // 0..1: onde fica o ponto médio
  const descricao = temPreco
    ? faixa > 0
      ? `Preço por embalagem: de ${reais(min!)} a ${reais(max!)}, médio ${reais(med!)}`
      : `Preço por embalagem: ${reais(med!)}, encontrado em uma loja`
    : "Preço ainda em pesquisa";
  const classes = ["orc-cota", carregando || !temPreco ? "orc-cota--carregando" : "", chegou ? "orc-cota--chegou" : ""];

  return (
    <figure className={classes.join(" ").trim()} role="img" aria-label={descricao}>
      <div className="orc-cota__linha" aria-hidden="true">
        <span className="orc-cota__ponta">{temPreco && faixa > 0 ? reaisCurto(min!) : ""}</span>
        <div className="orc-cota__trilho">
          {/* o texto do médio fica preso entre 20% e 80% para não vazar da cota quando o médio encosta numa ponta */}
          <div className="orc-cota__medio" style={{ left: `${Math.min(Math.max(posicao, 0.2), 0.8) * 100}%` }}>
            {temPreco ? (faixa > 0 ? <>médio <strong>{reais(med!)}</strong></> : <strong>{reais(med!)}</strong>)
                      : <span className="orc-cota__vazio">pesquisando preço</span>}
          </div>
          <svg className="orc-cota__svg" viewBox="0 0 100 20" preserveAspectRatio="none" focusable="false">
            <line className="orc-cota__chamada" x1="0" y1="2" x2="0" y2="18" vectorEffect="non-scaling-stroke" />
            <line className="orc-cota__chamada" x1="100" y1="2" x2="100" y2="18" vectorEffect="non-scaling-stroke" />
            {temPreco ? (
              <line className="orc-cota__traco" x1="0" y1="10" x2="100" y2="10" vectorEffect="non-scaling-stroke" />
            ) : (
              <line className="orc-cota__oculta" x1="0" y1="10" x2="100" y2="10" vectorEffect="non-scaling-stroke" />
            )}
          </svg>
          {/* marcas a 45° e ponto médio em HTML: não deformam quando a cota estica com a largura */}
          <i className="orc-cota__marca orc-cota__marca--ini" />
          <i className="orc-cota__marca orc-cota__marca--fim" />
          {temPreco && <i className="orc-cota__ponto" style={{ left: `${posicao * 100}%` }} />}
        </div>
        <span className="orc-cota__ponta orc-cota__ponta--fim">{temPreco && faixa > 0 ? reaisCurto(max!) : ""}</span>
      </div>
      {rotulo && <figcaption className="orc-cota__rotulo">{rotulo}</figcaption>}
    </figure>
  );
}
