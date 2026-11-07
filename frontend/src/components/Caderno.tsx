"use client";

import { useMemo, useReducer, useState } from "react";
import {
  contarErros,
  errosPorId,
  estadoInicial,
  primeiroErro,
  reduzir,
  type Linha,
  type ModoEntrada,
} from "@/lib/lista";
import { formatarCep, gerarUuid } from "@/lib/validacao";
import { NovaObra, type Obra, type RascunhoObra } from "./NovaObra";
import { Importador } from "./Importador";
import { TabelaMateriais, idCampo } from "./TabelaMateriais";

const MODOS: { id: ModoEntrada; rotulo: string; etapa: string | null }[] = [
  { id: "manual", rotulo: "Cadastro manual", etapa: null },
  { id: "csv", rotulo: "CSV", etapa: null },
  { id: "excel", rotulo: "Excel", etapa: "09" },
  { id: "revit", rotulo: "TXT do Revit", etapa: "10" },
  { id: "pdf", rotulo: "PDF com texto", etapa: "11" },
];

const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function Caderno() {
  const [obra, setObra] = useState<Obra | null>(null);
  const [editandoObra, setEditandoObra] = useState(false);
  const [orcamentoId, setOrcamentoId] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState<RascunhoObra>({ nome: "", cep: "", orcamento: "" });
  const [lista, despachar] = useReducer(reduzir, estadoInicial);

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

  function irParaPrimeiroErro() {
    despachar({ tipo: "revelar_erros" });
    const alvo = primeiroErro(lista.linhas, erros);
    if (alvo) requestAnimationFrame(() => document.getElementById(idCampo(alvo.id, alvo.campo))?.focus());
  }

  const mostrandoFormulario = !obra || editandoObra;
  const modoAtual = MODOS.find((m) => m.id === lista.modo)!;

  return (
    <main className="pagina">
      <header className="topo">
        <p className="marca">Orça</p>
        <p className="lema">Caderno de materiais</p>
      </header>

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
              ) : (
                <p className="apoio">Digite os materiais um a um. Quantidade aceita vírgula decimal (12,5) e a unidade aceita m².</p>
              )}
              <Importador
                mostrarArquivo={lista.modo === "csv"}
                linhasExistentes={itensPreenchidos}
                novoId={gerarUuid}
                onAplicar={aplicarImportacao}
              />
            </div>

            <TabelaMateriais estado={lista} erros={erros} despachar={despachar} novoId={gerarUuid} />
          </section>

          <section className="duas-colunas" aria-label="Sugestões da revisão">
            <div className="folha reservada-area" aria-labelledby="titulo-e1">
              <p className="secao-etiqueta">Avisos E1</p>
              <h2 id="titulo-e1" className="titulo-menor">
                Possíveis erros na lista
              </h2>
              <p className="apoio">Nenhum aviso por enquanto. As correções propostas aparecem aqui na etapa 05, com um clique para aceitar.</p>
            </div>
            <div className="folha reservada-area" aria-labelledby="titulo-e2">
              <p className="secao-etiqueta">Complementos E2</p>
              <h2 id="titulo-e2" className="titulo-menor">
                Itens que costumam faltar
              </h2>
              <p className="apoio">Complementos como argamassa e rejunte aparecem aqui na etapa 06, sempre como proposta.</p>
            </div>
          </section>

          <section className="envio" aria-label="Envio">
            <div>
              <button type="button" className="botao-primario grande" disabled={envioBloqueado} aria-describedby="motivo-envio">
                Enviar para a IA
              </button>
              <p id="motivo-envio" className="nota" role="status">
                {semItens
                  ? "Adicione ao menos um material para enviar."
                  : totalErros > 0
                    ? `Corrija ${totalErros} ${totalErros === 1 ? "campo" : "campos"} para liberar o envio.`
                    : "Lista válida. O envio será ligado na etapa 08."}
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
