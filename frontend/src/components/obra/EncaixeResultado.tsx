"use client";

// ENCAIXE DA FATIA C (João): painel de totais, "cabe ou não", frete e economia, ganho de tempo e botão Exportar.
// Aqui fica só o esqueleto com os três estados que a tela precisa (calculando, pronto e sem total confiável).
// João substitui o miolo por componentes de frontend/src/components/resultado/, mantendo estas props.
// Frete está em pausa: `logistica.frete_total` é sempre 0 por enquanto.

import type { Orcamento } from "@/lib/orcamento/tipos";

export function EncaixeResultado({ orcamento }: { orcamento: Orcamento }) {
  const { logistica, viabilidade, ganho } = orcamento;
  const calculando = !logistica && !viabilidade && !ganho;

  return (
    <section className="obra-bloco" aria-labelledby="obra-resultado-c" data-encaixe="fatia-c">
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
        <>
          {viabilidade && (
            <>
              {viabilidade.completo === false && (
                <p className="obra-bloco__aviso" role="note">
                  Ainda não dá para afirmar se cabe no orçamento: há itens sem preço e o total é só um piso.
                </p>
              )}
              {viabilidade.resumo && <p className="obra-bloco__texto">{viabilidade.resumo}</p>}
            </>
          )}
          {ganho?.resumo && <p className="obra-bloco__texto">{ganho.resumo}</p>}
        </>
      )}
    </section>
  );
}
