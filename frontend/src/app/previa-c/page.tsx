"use client";

// Prévia da estimativa com dados FICTÍCIOS (sem banco): /previa-c?cenario=cabe|nao-cabe|parcial
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CENARIOS } from "@/components/resultado/exemplos";
import { EstimativaView } from "@/components/resultado/EstimativaView";

function Previa() {
  const q = useSearchParams().get("cenario") ?? "cabe";
  const c = CENARIOS[q] ?? CENARIOS.cabe;
  return (
    <>
      <nav className="sh-apoio" aria-label="Cenários de exemplo" style={{ display: "flex", gap: 12, margin: "0 0 8px" }}>
        <b>Prévia · dados fictícios:</b>
        {Object.entries(CENARIOS).map(([k, v]) => (
          <a key={k} className="sh-link" href={`?cenario=${k}`} aria-current={k === q ? "page" : undefined} style={{ fontWeight: k === q ? 600 : 400 }}>
            {v.rotulo}
          </a>
        ))}
      </nav>
      <EstimativaView orcamento={c.orcamento} itens={c.itens} />
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
