"use client";

// Tela de estimativa (Figma 05 Materiais, 06 Fontes, 08 Documento): só desenha. Recebe o orçamento e os itens já lidos
// (do useOrcamento na página real, de dados de exemplo na prévia).
import { useEffect, useMemo, useState } from "react";
import { reais, linkDiretoProduto } from "../orcamento/formato";
import { ImagemProduto } from "../imagens/ImagemProduto";
import { CabecalhoPagina } from "../shell/CabecalhoPagina";
import type { ItemLinha, Orcamento } from "@/lib/orcamento/tipos";
import { BlocoViabilidade } from "./BlocoViabilidade";
import { DocumentoOrcamento } from "./DocumentoOrcamento";
import { LojasProximas } from "./LojasProximas";
import { contagem, foraDoSubtotal, itensParaTela, linhasDocumento, linkRaciocinio, mesAno, subtotal, tituloEditorial, urlExportar } from "./resultado";
import "./resultado.css";

export function EstimativaView({ orcamento, itens }: { orcamento: Orcamento; itens: ItemLinha[] }) {
  const [aba, setAba] = useState<"materiais" | "fontes">("materiais");
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [documento, setDocumento] = useState(false);

  const lista = useMemo(() => itensParaTela(itens), [itens]);
  const linhas = useMemo(() => linhasDocumento(itens), [itens]);
  const fora = useMemo(() => foraDoSubtotal(itens), [itens]);
  const item = lista.find((i) => i.id === selecionado) ?? lista[0];
  const fontes = lista.filter((i) => i.situacao === "precificado").flatMap((i) => i.fontes.map((f) => ({ ...f, item: i.nome, chave: `${i.id}-${f.dominio}` })));

  useEffect(() => {
    if (selecionado && !lista.some((i) => i.id === selecionado)) setSelecionado(null);
  }, [lista, selecionado]);

  const { titulo, destaque } = tituloEditorial(orcamento.nome);
  const excel = urlExportar(orcamento.id);
  const pdf = urlExportar(orcamento.id, undefined, "pdf");
  const raciocinio = linkRaciocinio(orcamento.trace_url);
  const cep = orcamento.cep.replace(/^(\d{5})(\d{3})$/, "$1-$2");

  return (
    <>
      <CabecalhoPagina
        trilha={[{ rotulo: "Estimativas", href: "/projetos" }, { rotulo: orcamento.nome }, { rotulo: "Atual" }]}
        etiqueta={`Caderno de materiais · ${mesAno(orcamento.created_at)}`}
        titulo={titulo}
        destaque={destaque}
        apoio={`CEP ${cep} · ${orcamento.qtd_itens} ${orcamento.qtd_itens === 1 ? "item" : "itens"} na lista`}
        acao={
          <div className="sh-subtotal">
            <p className="sh-etiqueta" style={{ margin: 0 }}>
              Subtotal estimado
            </p>
            <span className="valor">{reais(subtotal(linhas))}</span>
            {/* Junto do valor que a IA calculou: é o registro das buscas e fontes por trás desse número. */}
            {raciocinio ? (
              <a
                className="sh-link"
                href={raciocinio}
                target="_blank"
                rel="noopener noreferrer"
                title="Abre em nova aba o registro de cada busca, conferência e fonte que o agente usou"
                style={{ display: "block", marginTop: 4 }}
              >
                Ver o raciocínio da IA <span aria-hidden="true">↗</span>
              </a>
            ) : null}
            <p className="sh-apoio" style={{ fontSize: 10, marginBottom: 8 }}>
              {contagem(linhas.length, "material", "materiais").replace(/^0/, "")}
            </p>
            <button type="button" className="sh-botao" onClick={() => setDocumento(true)}>
              Prévia do documento <span aria-hidden="true">↗</span>
            </button>
            {excel ? (
              <a className="sh-link" href={excel} download="plano-de-compra.xlsx" style={{ display: "block", marginTop: 8 }}>
                Baixar plano em Excel ↓
              </a>
            ) : null}
            {pdf ? (
              <a className="sh-link" href={pdf} download="plano-de-compra.pdf" style={{ display: "block", marginTop: 8 }}>
                Baixar plano em PDF ↓
              </a>
            ) : null}
          </div>
        }
      />

      <p className="sh-resumo">
        <span className="ok">{contagem(linhas.length, "item precificado", "itens precificados")}</span>
        <span className="pend">{contagem(fora.total, "item pendente", "itens pendentes")}</span>
      </p>

      <LojasProximas cep={orcamento.cep} />

      <div className="sh-duas">
        <div>
          <div className="sh-abas" role="tablist" aria-label="Seções da estimativa">
            <button type="button" role="tab" className="sh-aba" aria-selected={aba === "materiais"} onClick={() => setAba("materiais")}>
              Materiais · {String(lista.length).padStart(2, "0")}
            </button>
            <button type="button" role="tab" className="sh-aba" aria-selected={aba === "fontes"} onClick={() => setAba("fontes")}>
              Fontes · {String(fontes.length).padStart(2, "0")}
            </button>
          </div>

          {lista.length === 0 && <p className="sh-apoio" role="status">Os itens aparecem aqui conforme a IA os encontra.</p>}

          {aba === "materiais" ? (
            <div role="tabpanel">
              {lista.map((i) => (
                <button key={i.id} type="button" className="sh-item" aria-pressed={item?.id === i.id} onClick={() => setSelecionado(i.id)}>
                  <span className="foto">
                    <ImagemProduto src={i.imagem} nome={i.nome} carregando={i.situacao === "buscando"} />
                  </span>
                  <span>
                    <span className={`nome${item?.id === i.id ? " sel" : ""}`}>{i.nome}</span>
                    {i.detalhe && <small>{i.detalhe}</small>}
                    {i.loja && <small>{i.loja}</small>}
                  </span>
                  <span className="qtd-col" style={{ fontSize: 12 }}>{i.quantidade}</span>
                  <span className="preco">
                    {i.total === null ? (
                      <span className="sh-aviso" style={{ fontWeight: 400, fontSize: 11 }}>
                        {i.situacao === "buscando" ? "Buscando…" : i.situacao === "pendente" ? "Revisar especificação ↗" : "Sem preço"}
                      </span>
                    ) : (
                      <>
                        {reais(i.total)}
                        <small>{i.unitario}</small>
                      </>
                    )}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div role="tabpanel">
              {fontes.length === 0 && <p className="sh-apoio">Nenhuma fonte ainda.</p>}
              {fontes.map((f) => (
                <div key={f.chave} className="sh-fonte">
                  <span>
                    {f.loja}
                    <small style={{ display: "block" }}>
                      {f.item} · {f.url && linkDiretoProduto(f.url) ? <a className="sh-link" href={f.url} target="_blank" rel="noopener noreferrer">Ver produto em {f.dominio}</a> : "Link direto indisponível. Pesquise este item novamente."}
                    </small>
                    {f.data && <small style={{ display: "block" }}>{f.data}</small>}
                  </span>
                  <strong style={{ fontSize: 13 }}>{f.preco}</strong>
                </div>
              ))}
            </div>
          )}
        </div>

        <aside className="sh-lateral sh-ref" aria-label="Referência selecionada">
          {item ? (
            <>
              <p className="sh-etiqueta" style={{ marginTop: 0 }}>
                Referência selecionada <span style={{ float: "right" }}>{String(lista.indexOf(item) + 1).padStart(2, "0")} / {String(lista.length).padStart(2, "0")}</span>
              </p>
              <div className="imagem"><ImagemProduto src={item.imagem} nome={item.nome} carregando={item.situacao === "buscando"} destaque /></div>
              <h3>{item.nome}</h3>
              <p className="sh-apoio">{item.loja}</p>
              {item.situacao === "precificado" ? (
                <p style={{ fontSize: 20, margin: "8px 0 0" }}>{item.unitario}</p>
              ) : (
                <p className="sh-aviso" style={{ fontSize: 13 }}>{item.aviso}</p>
              )}
              <dl>
                <dt>Unidade da oferta</dt>
                <dd>{item.detalhe || "—"}</dd>
                <dt>Quantidade para a obra</dt>
                <dd>{[item.compra, item.quantidade].filter(Boolean).join(" · ") || "—"}</dd>
                <dt>Fontes e fornecedores</dt>
                <dd>{item.fontes.length ? item.fontes.map((f) => f.dominio).join(", ") : "A confirmar com o fornecedor"}</dd>
              </dl>
            </>
          ) : (
            <p className="sh-apoio">Selecione um material.</p>
          )}
          <div className="rs-lateral-viab">
            <BlocoViabilidade orcamento={orcamento} />
          </div>
        </aside>
      </div>

      {documento && <DocumentoOrcamento orcamento={orcamento} itens={itens} onFechar={() => setDocumento(false)} />}
    </>
  );
}
