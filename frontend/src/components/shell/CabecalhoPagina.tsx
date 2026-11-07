import Link from "next/link";
import type { ReactNode } from "react";

export type Migalha = { rotulo: string; href?: string };

/** Cabeçalho editorial de cada tela: trilha, etiqueta, título serifado com palavra em itálico e ação à direita. */
export function CabecalhoPagina({
  trilha,
  etiqueta,
  titulo,
  destaque,
  apoio,
  acao,
}: {
  trilha: Migalha[];
  etiqueta?: string;
  titulo?: string;
  destaque?: string;
  apoio?: ReactNode;
  acao?: ReactNode;
}) {
  return (
    <header className="sh-cabecalho">
      <div>
        <p className="sh-trilha">
          {trilha.map((m, i) => (
            <span key={m.rotulo}>
              {i > 0 && " / "}
              {m.href ? <Link href={m.href}>{m.rotulo}</Link> : <b>{m.rotulo}</b>}
            </span>
          ))}
        </p>
        {etiqueta && <p className="sh-etiqueta">{etiqueta}</p>}
        {titulo && (
          <h1 className="sh-titulo">
            {titulo} {destaque && <em>{destaque}</em>}
          </h1>
        )}
        {apoio && <p className="sh-apoio">{apoio}</p>}
      </div>
      {acao}
    </header>
  );
}
