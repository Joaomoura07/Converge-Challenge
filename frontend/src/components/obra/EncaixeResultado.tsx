"use client";

// ENCAIXE DA FATIA C (João): painel de totais, "cabe ou não", frete e economia, ganho de tempo e botão Exportar.
// Aqui fica só o esqueleto com os três estados que a tela precisa (calculando, pronto e sem total confiável).
// O miolo agora é PainelResultado (frontend/src/components/resultado/). Props: orcamento + itens (opcional).
// Frete está em pausa: `logistica.frete_total` é sempre 0 por enquanto.

import { PainelResultado } from "@/components/resultado/PainelResultado";
import type { ItemLinha, Orcamento } from "@/lib/orcamento/tipos";

export function EncaixeResultado({ orcamento, itens = [] }: { orcamento: Orcamento; itens?: ItemLinha[] }) {
  const { logistica, viabilidade, ganho } = orcamento;
  const calculando = !logistica && !viabilidade && !ganho;

  return (
    <section className="obra-bloco" aria-labelledby="obra-resultado-c">
      <h2 id="obra-resultado-c" className="obra-bloco__titulo">
        Estimativa e plano de compra
      </h2>

      {calculando ? (
        <p className="obra-bloco__texto" role="status" aria-live="polite">
          {orcamento.status_pesquisa === "falhou"
            ? "A pesquisa não terminou, por isso o resultado ainda não foi calculado."
            : "Calculando frete, viabilidade e ganho de tempo quando a pesquisa terminar…"}
        </p>
      ) : (
        <PainelResultado orcamento={orcamento} itens={itens} />
      )}
    </section>
  );
}
