"use client";

// ENCAIXE DA FATIA C na página /obra/[id]: a estimativa completa (telas 05, 06 e 08 do Figma) fica em /estimativa/[id].
// Aqui só o estado ("calculando…") e o atalho. Frete está em pausa: `logistica.frete_total` é sempre 0 por enquanto.

import Link from "next/link";
import { reais } from "@/components/orcamento/formato";
import { foraDoSubtotal, linhasDocumento, linkRaciocinio, subtotal, veredito } from "@/components/resultado/resultado";
import type { ItemLinha, Orcamento } from "@/lib/orcamento/tipos";

export function EncaixeResultado({ orcamento, itens = [] }: { orcamento: Orcamento; itens?: ItemLinha[] }) {
  const { logistica, viabilidade, ganho } = orcamento;
  const calculando = !logistica && !viabilidade && !ganho;
  const linhas = linhasDocumento(itens);
  const ver = viabilidade ? veredito(viabilidade) : null;
  const raciocinio = linkRaciocinio(orcamento.trace_url);

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
        <>
          <dl className="obra-resumo">
            <div>
              <dt>Subtotal estimado</dt>
              <dd className="obra-resumo__valor">{reais(subtotal(linhas))}</dd>
              <dd className="obra-resumo__nota">
                {foraDoSubtotal(itens).total === 0
                  ? "Todos os itens com preço"
                  : `${foraDoSubtotal(itens).total} ${foraDoSubtotal(itens).total === 1 ? "item fora" : "itens fora"} do subtotal`}
              </dd>
            </div>
            {ver && (
              <div data-tom={ver.tom}>
                <dt>Orçamento do cliente {reais(viabilidade?.orcamento_cliente ?? orcamento.orcamento_cliente)}</dt>
                <dd className="obra-resumo__veredito">
                  <span aria-hidden="true">{ver.icone}</span> {ver.titulo}
                </dd>
              </div>
            )}
            {ganho?.resumo && (
              <div>
                <dt>Ganho de tempo</dt>
                <dd className="obra-resumo__nota">{ganho.resumo}</dd>
              </div>
            )}
          </dl>
          <div className="obra-acoes">
            <Link href={`/estimativa/${orcamento.id}`} className="sh-botao">
              Ver estimativa completa <span aria-hidden="true">↗</span>
            </Link>
            {raciocinio ? (
              <a
                className="sh-link"
                href={raciocinio}
                target="_blank"
                rel="noopener noreferrer"
                title="Abre em nova aba o registro de cada busca, conferência e fonte que o agente usou"
              >
                Ver o raciocínio da IA <span aria-hidden="true">↗</span>
              </a>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}
