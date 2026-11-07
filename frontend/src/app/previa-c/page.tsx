"use client";

// Prévia da Fatia C (dados fictícios, sem banco): /previa-c?cenario=cabe|nao-cabe|parcial
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PainelResultado } from "@/components/resultado/PainelResultado";
import { CENARIOS } from "@/components/resultado/exemplos";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import "../obra/[id]/obra.css";

function Previa() {
  const q = useSearchParams().get("cenario") ?? "cabe";
  const c = CENARIOS[q] ?? CENARIOS.cabe;
  return (
    <>
      <CabecalhoPagina trilha={[{ rotulo: "Prévia" }, { rotulo: "Resultado da Fatia C" }]} etiqueta="Dados fictícios" titulo="Resultado da" destaque="estimativa." apoio={c.rotulo} />
      <nav className="sh-apoio" aria-label="Cenários" style={{ display: "flex", gap: 12, margin: "8px 0" }}>
        {Object.entries(CENARIOS).map(([k, v]) => (
          <a key={k} className="sh-link" href={`?cenario=${k}`} aria-current={k === q ? "page" : undefined} style={{ fontWeight: k === q ? 600 : 400 }}>
            {v.rotulo}
          </a>
        ))}
      </nav>
      <section className="obra-bloco">
        <h2 className="obra-bloco__titulo">Estimativa e plano de compra</h2>
        <PainelResultado orcamento={c.orcamento} itens={c.itens} />
      </section>
    </>
  );
}

export default function PreviaC() {
  return (
    <Suspense>
      <Previa />
    </Suspense>
  );
}
