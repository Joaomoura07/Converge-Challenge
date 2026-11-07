"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import { PASSOS_PESQUISA } from "@/lib/prototipo";

// Tela 04 · Pesquisa (simulação por tempo; o acompanhamento real virá do useOrcamento)
export default function Pesquisa() {
  const [passo, setPasso] = useState(0);

  useEffect(() => {
    if (passo >= PASSOS_PESQUISA.length) return;
    const t = setTimeout(() => setPasso((p) => p + 1), 1300);
    return () => clearTimeout(t);
  }, [passo]);

  const pronto = passo >= PASSOS_PESQUISA.length;

  return (
    <>
      <CabecalhoPagina
        trilha={[{ rotulo: "Estimativa", href: "/nova" }, { rotulo: "Residência Aurora" }, { rotulo: "03 de 03" }]}
        etiqueta="Pesquisa de demonstração"
        titulo="Referências para"
        destaque="cada escolha."
        apoio="Uma simulação de como a pesquisa organiza preços, unidades e pendências."
      />

      <div className="sh-duas">
        <div>
          <p className="sh-apoio" role="status" style={{ marginBottom: 8 }}>
            {pronto ? "Pesquisa concluída" : "Lendo sua lista de materiais"}
          </p>
          <ol className="sh-passos">
            {PASSOS_PESQUISA.map((p, i) => (
              <li key={p.t} className={i < passo ? "feito" : i === passo ? "ativo" : undefined}>
                <span className="num">{String(i + 1).padStart(2, "0")}</span>
                <span>
                  <strong>{p.t}</strong>
                  <span>{p.d}</span>
                </span>
              </li>
            ))}
          </ol>
          <div className="sh-rodape-acoes">
            <Link href="/revisar" className="sh-link">
              ← Revisar a lista
            </Link>
            <Link href="/estimativa" className="sh-botao" aria-disabled={!pronto} tabIndex={pronto ? 0 : -1}>
              Ver estimativa <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>

        <aside className="sh-painel-escuro" aria-label="Atividade da simulação">
          <h3>Atividade / simulação</h3>
          <p>Dados sintéticos. Nenhuma loja real foi consultada.</p>
        </aside>
      </div>
    </>
  );
}
