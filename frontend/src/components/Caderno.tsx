"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import {
  contarErros,
  errosPorId,
  estadoInicial,
  primeiroErro,
  reduzir,
  type Linha,
  type ModoEntrada,
} from "@/lib/lista";
import { useSugestoes } from "@/lib/revisao/useSugestoes";
import { formatarCep, gerarUuid } from "@/lib/validacao";
import { CabecalhoPagina } from "./shell/CabecalhoPagina";
import { PainelSugestoes } from "./PainelSugestoes";
import { NovaObra, type Obra, type RascunhoObra } from "./NovaObra";
import { iniciarEnvio } from "@/lib/envio/armazem";
import { conteudoDoEnvio, montarCorpo } from "@/lib/envio/corpo";
import { lerRascunho, salvarRascunho } from "@/lib/envio/rascunho";
import { Importador } from "./Importador";
import { TabelaMateriais, idCampo } from "./TabelaMateriais";

const MODOS: { id: ModoEntrada; rotulo: string; etapa: string | null }[] = [
  { id: "manual", rotulo: "Cadastro manual", etapa: null },
  { id: "csv", rotulo: "CSV", etapa: null },
  { id: "excel", rotulo: "Excel", etapa: null },
  { id: "revit", rotulo: "TXT do Revit", etapa: null },
  { id: "pdf", rotulo: "PDF com texto", etapa: null },
];

const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function Caderno() {
  const [obra, setObra] = useState<Obra | null>(null);
  const [editandoObra, setEditandoObra] = useState(false);
  const [orcamentoId, setOrcamentoId] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState<RascunhoObra>({ nome: "", cep: "", orcamento: "" });
  const [lista, despachar] = useReducer(reduzir, estadoInicial);
  const router = useRouter();
  // último pedido enviado com o código atual: se o conteúdo mudar depois, o próximo envio ganha código novo
  const ultimoEnvio = useRef<{ orcamentoId: string; conteudo: string } | null>(null);

  // "Voltar e corrigir": a página do resultado traz de volta o rascunho guardado no momento do envio.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("retomar");
    if (!id) return;
    const r = lerRascunho(id);
    window.history.replaceState(null, "", window.location.pathname);
    if (!r) return;
    setObra(r.obra);
    setOrcamentoId(r.orcamentoId);
    setRascunho({ nome: r.obra.nome, cep: r.obra.cep, orcamento: String(r.obra.orcamentoCliente).replace(".", ",") });
    despachar({ tipo: "importar", linhas: r.linhas, como: "substituir" });
    despachar({ tipo: "alternar_modo", modo: r.modo as ModoEntrada });
    despachar({ tipo: "revelar_erros" });
    ultimoEnvio.current = r.ultimoEnvio;
  }, []);

  const { estado: revisor, repetir: repetirRevisao } = useSugestoes(lista.linhas);
  const erros = useMemo(() => errosPorId(lista.linhas), [lista.linhas]);
  const totalErros = contarErros(erros);
  const semItens = lista.linhas.length === 0;
  const envioBloqueado = semItens || totalErros > 0;
  const itensPreenchidos = lista.linhas.filter((l) => l.descricao || l.quantidade || l.unidade || l.categoria).length;

  function aplicarImportacao(linhas: Linha[], como: "acrescentar" | "substituir") {
    despachar({ tipo: "importar", linhas, como });
    // Mostra já os campos que o arquivo deixou em branco ou inválidos.
    despachar({ tipo: "revelar_erros" });
  }

  function iniciar(nova: Obra) {
    setObra(nova);
    setEditandoObra(false);
    // O ID nasce uma vez, ao iniciar a obra, e é mantido mesmo se os dados da obra forem editados.
    setOrcamentoId((atual) => atual ?? gerarUuid());
  }

  /** "Enviar para a IA": guarda o rascunho, começa o POST (que também pesquisa) e vai para o resultado ao vivo. */
  function enviar() {
    if (!obra || !orcamentoId || envioBloqueado) return;
    let id = orcamentoId;
    let corpo = montarCorpo({ orcamentoId: id, obra, linhas: lista.linhas, modo: lista.modo });
    if (!corpo) return;
    const conteudo = conteudoDoEnvio(corpo);
    // Mesmo código com conteúdo diferente daria conflito (409): um pedido novo recebe um código novo.
    if (ultimoEnvio.current && ultimoEnvio.current.orcamentoId === id && ultimoEnvio.current.conteudo !== conteudo) {
      id = gerarUuid();
      setOrcamentoId(id);
      corpo = { ...corpo, orcamento_id: id };
    }
    ultimoEnvio.current = { orcamentoId: id, conteudo };
    salvarRascunho({ obra, orcamentoId: id, modo: lista.modo, linhas: lista.linhas, ultimoEnvio: ultimoEnvio.current });
    void iniciarEnvio(corpo);
    router.push(`/obra/${id}`);
  }

  function irParaPrimeiroErro() {
    despachar({ tipo: "revelar_erros" });
    const alvo = primeiroErro(lista.linhas, erros);
    if (alvo) requestAnimationFrame(() => document.getElementById(idCampo(alvo.id, alvo.campo))?.focus());
  }

  const mostrandoFormulario = !obra || editandoObra;
  const modoAtual = MODOS.find((m) => m.id === lista.modo)!;

  return (
    <main className="pagina">
      <CabecalhoPagina
        trilha={[{ rotulo: "Projetos", href: "/projetos" }, { rotulo: "Nova estimativa" }, { rotulo: "01 de 03" }]}
        etiqueta="Preparação / lista de materiais"
        titulo={mostrandoFormulario ? "Do desenho ao" : undefined}
        destaque={mostrandoFormulario ? "quantitativo." : undefined}
        apoio={mostrandoFormulario ? "Um bom orçamento começa com uma lista bem especificada." : undefined}
      />

      {mostrandoFormulario ? (
        <NovaObra
          rascunho={rascunho}
          onRascunho={setRascunho}
          onIniciar={iniciar}
          editando={Boolean(obra)}
        />
      ) : (
        <section className="resumo-obra" aria-label="Obra iniciada">
          <div>
            <p className="secao-etiqueta">Obra</p>
            <h1 className="titulo-obra">{obra.nome}</h1>
            <dl className="dados">
              <div>
                <dt>CEP</dt>
                <dd>{formatarCep(obra.cep)}</dd>
              </div>
              <div>
                <dt>Orçamento do cliente</dt>
                <dd>{reais.format(obra.orcamentoCliente)}</dd>
              </div>
              <div>
                <dt>Código do orçamento</dt>
                <dd className="mono" data-testid="orcamento-id">
                  {orcamentoId}
                </dd>
              </div>
            </dl>
          </div>
          <button type="button" className="botao-secundario" onClick={() => setEditandoObra(true)}>
            Editar dados da obra
          </button>
        </section>
      )}

      {obra && !editandoObra && (
        <>
          <section className="folha" aria-labelledby="titulo-materiais">
            <p className="secao-etiqueta">2 · Materiais</p>
            <h2 id="titulo-materiais" className="titulo-secao">
              Lista de revisão
            </h2>

            <div className="modos" role="tablist" aria-label="Como adicionar materiais">
              {MODOS.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  role="tab"
                  id={`modo-${m.id}`}
                  aria-selected={lista.modo === m.id}
                  aria-controls="painel-modo"
                  className={`modo${lista.modo === m.id ? " ativo" : ""}`}
                  onClick={() => despachar({ tipo: "alternar_modo", modo: m.id })}
                >
                  {m.rotulo}
                </button>
              ))}
            </div>

            <div id="painel-modo" role="tabpanel" aria-labelledby={`modo-${lista.modo}`} className="painel-modo">
              {modoAtual.etapa ? (
                <p className="apoio">
                  A importação de <strong>{modoAtual.rotulo}</strong> chega na etapa {modoAtual.etapa}. Os materiais já digitados
                  continuam na lista abaixo e serão a mesma lista quando a importação existir.
                </p>
              ) : lista.modo === "csv" ? (
                <p className="apoio">
                  Envie um CSV exportado do Excel ou de outro programa. Cada linha vira um item editável na tabela abaixo, com a linha do arquivo de origem.
                </p>
              ) : lista.modo === "excel" ? (
                <p className="apoio">
                  Envie uma planilha .xlsx, .xls ou .xlsm. Se houver várias abas com dados, você escolhe qual importar. Cada linha vira um item editável, com a linha da planilha de origem.
                </p>
              ) : lista.modo === "pdf" ? (
                <p className="apoio">
                  Envie um PDF com texto (pedido de cotação ou quadro de acabamentos). A leitura reconstrói a tabela pela posição do texto: confira cada linha antes de enviar, principalmente quando a quantidade vier em embalagens. PDF escaneado não funciona; use CSV, Excel ou digite os materiais.
                </p>
              ) : lista.modo === "revit" ? (
                <p className="apoio">
                  No Revit, exporte a tabela de quantitativos como texto (.txt, separado por tabulação). Títulos, grupos como &quot;Nível: Térreo&quot;, subtotais e o total geral são tratados: só as linhas de itens entram, com o nível do grupo.
                </p>
              ) : (
                <p className="apoio">Digite os materiais um a um. Quantidade aceita vírgula decimal (12,5) e a unidade aceita m².</p>
              )}
              <Importador
                modo={lista.modo}
                linhasExistentes={itensPreenchidos}
                novoId={gerarUuid}
                onAplicar={aplicarImportacao}
              />
            </div>

            <TabelaMateriais estado={lista} erros={erros} despachar={despachar} novoId={gerarUuid} />
          </section>

          <section className="duas-colunas" aria-label="Sugestões da revisão">
            <PainelSugestoes lista={lista} despachar={despachar} revisor={revisor} repetir={repetirRevisao} novoId={gerarUuid} />
          </section>

          <section className="envio" aria-label="Envio">
            <div>
              <button type="button" className="botao-primario grande" disabled={envioBloqueado} aria-describedby="motivo-envio" onClick={enviar}>
                Enviar para a IA
              </button>
              <p id="motivo-envio" className="nota" role="status">
                {semItens
                  ? "Adicione ao menos um material para enviar."
                  : totalErros > 0
                    ? `Corrija ${totalErros} ${totalErros === 1 ? "campo" : "campos"} para liberar o envio.`
                    : "Lista válida. Ao enviar, a pesquisa começa e você acompanha o resultado ao vivo."}
              </p>
            </div>
            {totalErros > 0 && (
              <button type="button" className="botao-link" onClick={irParaPrimeiroErro}>
                Ir para o primeiro erro
              </button>
            )}
          </section>
        </>
      )}
    </main>
  );
}
