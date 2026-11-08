"use client";

import { useState, type Dispatch } from "react";
import type { Acao, EstadoLista } from "@/lib/lista";
import { aplicarCorrecao, complementoParaLinha, planejarAceiteTodas, quantidadeParaTexto } from "@/lib/revisao/aplicar";
import type { EstadoRevisor } from "@/lib/revisao/revisor";
import type { ComplementoSugerido, ErroRevisao } from "@/lib/revisao/tipos";
import { idCampo } from "./TabelaMateriais";

type Props = {
  lista: EstadoLista;
  despachar: Dispatch<Acao>;
  revisor: EstadoRevisor;
  repetir: () => void;
  novoId: () => string;
};

const ROTULO_REGRA: Record<string, string> = {
  unidade: "Unidade",
  quantidade: "Quantidade",
  duplicado: "Possível duplicata",
  colunas_trocadas: "Colunas trocadas",
};

const vazioTxt = (v: string) => (v.trim() === "" ? "(vazio)" : v);

function descreverProposta(e: ErroRevisao): string[] {
  const c = e.correcao;
  if (!c) return [];
  return [
    ...c.alteracoes.map(
      (a) => `Linha ${a.linha}: ${a.campo === "unidade" ? "unidade" : "quantidade"} ${vazioTxt(a.de)} → ${vazioTxt(a.para)}`,
    ),
    ...c.remover.map((r) => `Remover a linha ${r.linha}`),
  ];
}

function irParaLinha(id: string | null | undefined) {
  if (!id) return;
  document.getElementById(idCampo(id, "descricao"))?.focus();
}

export function PainelSugestoes({ lista, despachar, revisor, repetir, novoId }: Props) {
  const [aviso, setAviso] = useState("");
  const { dados, fase, desatualizada } = revisor;
  const semItens = !lista.linhas.some((l) => l.descricao.trim());
  const erros = (dados?.erros ?? []).filter((e) => !lista.decisoes[e.id]);
  const complementos = (dados?.complementos ?? []).filter((c) => !lista.decisoes[c.id]);
  const lendo = fase === "carregando" && !dados;
  const travado = desatualizada || fase === "carregando";

  function aceitarErro(e: ErroRevisao) {
    if (!e.correcao) return;
    despachar({ tipo: "aceitar_correcao", id: e.id, correcao: e.correcao });
    setAviso(`Correção aplicada: ${ROTULO_REGRA[e.regra] ?? e.regra}.`);
  }
  function aceitarComplemento(c: ComplementoSugerido) {
    despachar({ tipo: "aceitar_complemento", id: c.id, linha: complementoParaLinha(c, novoId()) });
    setAviso(`Complemento adicionado à lista: ${c.descricao}.`);
  }
  /** Aceita todas as correções que ainda se aplicam. A lista é simulada em sequência: se duas correções se atropelam,
   *  a segunda fica de fora (e continua na tela para você decidir) em vez de sobrescrever a primeira. */
  function aceitarTodasCorrecoes() {
    const { aplicar, restam } = planejarAceiteTodas(lista.linhas, erros);
    for (const e of aplicar) despachar({ tipo: "aceitar_correcao", id: e.id, correcao: e.correcao! });
    setAviso(
      `${aplicar.length} ${aplicar.length === 1 ? "correção aplicada" : "correções aplicadas"}.` +
        (restam.length > 0 ? ` ${restam.length} ${restam.length === 1 ? "ficou" : "ficaram"} para você decidir.` : ""),
    );
  }
  function aceitarTodosComplementos() {
    for (const c of complementos) {
      despachar({ tipo: "aceitar_complemento", id: c.id, linha: complementoParaLinha(c, novoId()) });
    }
    setAviso(`${complementos.length} ${complementos.length === 1 ? "complemento adicionado" : "complementos adicionados"} à lista.`);
  }
  const corrigiveis = planejarAceiteTodas(lista.linhas, erros).aplicar.length;

  function recusar(id: string, rotulo: string) {
    despachar({ tipo: "recusar_sugestao", id });
    setAviso(`Sugestão descartada: ${rotulo}. A lista não foi alterada.`);
  }

  const estadoVazio = (itens: number, textoSemItens: string, textoNenhum: string) => {
    if (semItens) return <p className="apoio">{textoSemItens}</p>;
    if (lendo) {
      return (
        <p className="apoio lendo" role="status" aria-busy="true">
          Revisando a lista…
        </p>
      );
    }
    if (fase === "erro_rede" && !dados) return null;
    if (itens === 0 && fase === "pronto" && textoNenhum) return <p className="apoio">{textoNenhum}</p>;
    return null;
  };

  const falhaRede = fase === "erro_rede" && (
    <div className="aviso-falha" role="alert">
      <p>{revisor.mensagem ?? "Não foi possível revisar a lista."} Sua lista não foi alterada.</p>
      <button type="button" className="botao-secundario" onClick={repetir}>
        Tentar de novo
      </button>
    </div>
  );

  return (
    <>
      <div className="folha reservada-area" aria-labelledby="titulo-e1" aria-busy={travado}>
        <p className="secao-etiqueta">Avisos E1</p>
        <h2 id="titulo-e1" className="titulo-menor">
          Possíveis erros na lista
          {erros.length > 0 && <span className="contagem"> · {erros.length}</span>}
        </h2>
        {falhaRede}
        {desatualizada && !semItens && (
          <p className="nota" role="status">
            A lista mudou; revisando de novo. As sugestões abaixo só podem ser aceitas depois disso.
          </p>
        )}
        {estadoVazio(erros.length, "Adicione materiais para a revisão começar.", "Nenhum possível erro encontrado.")}
        {corrigiveis > 1 && (
          <div className="sugestoes-todas">
            <button type="button" className="botao-primario" disabled={travado} onClick={aceitarTodasCorrecoes}>
              Aceitar todas as correções ({corrigiveis})
            </button>
            <span className="nota">Aplica só as que têm proposta automática. Você vê o resultado na tabela.</span>
          </div>
        )}
        <ul className="sugestoes" hidden={erros.length === 0}>
          {erros.map((e) => {
            const proposta = descreverProposta(e);
            const aplicavel = Boolean(e.correcao) && aplicarCorrecao(lista.linhas, e.correcao!) !== null;
            return (
              <li key={e.id} className="sugestao" data-sugestao-id={e.id} data-regra={e.regra}>
                <p className="sugestao-tipo">
                  {ROTULO_REGRA[e.regra] ?? e.regra}
                  <span className="sugestao-linhas">
                    {e.linhas.length === 1 ? ` · linha ${e.linhas[0]}` : ` · ${e.linhas.length} linhas`}
                  </span>
                </p>
                <p className="sugestao-texto">{e.texto}</p>
                {proposta.length > 0 && (
                  <details className="proposta" open={proposta.length <= 3}>
                    <summary>{proposta.length === 1 ? "Proposta" : `Proposta (${proposta.length} alterações)`}</summary>
                    <ul>
                      {proposta.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </details>
                )}
                <div className="sugestao-acoes">
                  <button
                    type="button"
                    className="botao-primario"
                    disabled={!aplicavel || travado}
                    onClick={() => aceitarErro(e)}
                    aria-label={`Aceitar a correção: ${ROTULO_REGRA[e.regra] ?? e.regra}, ${e.linhas.length === 1 ? `linha ${e.linhas[0]}` : `${e.linhas.length} linhas`}`}
                  >
                    Aceitar
                  </button>
                  <button
                    type="button"
                    className="botao-secundario"
                    onClick={() => recusar(e.id, ROTULO_REGRA[e.regra] ?? e.regra)}
                    aria-label={`Recusar a sugestão: ${ROTULO_REGRA[e.regra] ?? e.regra}, ${e.linhas.length === 1 ? `linha ${e.linhas[0]}` : `${e.linhas.length} linhas`}`}
                  >
                    Recusar
                  </button>
                  <button type="button" className="botao-link" onClick={() => irParaLinha(e.item_ids.find(Boolean))}>
                    Ir para a linha
                  </button>
                </div>
                {!e.correcao && <p className="nota">Sem proposta automática: corrija na tabela ou recuse o aviso.</p>}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="folha reservada-area" aria-labelledby="titulo-e2" aria-busy={travado}>
        <p className="secao-etiqueta">Complementos E2</p>
        <h2 id="titulo-e2" className="titulo-menor">
          Itens que costumam faltar
          {complementos.length > 0 && <span className="contagem"> · {complementos.length}</span>}
        </h2>
        {dados && !dados.complementos_disponiveis && (
          <div className="aviso-falha" role="status">
            <p>
              {dados.complementos_erro ?? "Não foi possível calcular os complementos agora."} A revisão de erros e o envio
              continuam funcionando.
            </p>
            <button type="button" className="botao-secundario" onClick={repetir}>
              Tentar de novo
            </button>
          </div>
        )}
        {estadoVazio(
          complementos.length,
          "Adicione materiais para ver o que costuma faltar.",
          dados && !dados.complementos_disponiveis ? "" : "Nenhum complemento sugerido para esta lista.",
        )}
        {complementos.length > 1 && (
          <div className="sugestoes-todas">
            <button type="button" className="botao-primario" disabled={travado} onClick={aceitarTodosComplementos}>
              Aceitar todos os complementos ({complementos.length})
            </button>
            <span className="nota">Entram na lista como linhas marcadas "Sugerido · aceito por você".</span>
          </div>
        )}
        <ul className="sugestoes" hidden={complementos.length === 0}>
          {complementos.map((c) => (
            <li key={c.id} className="sugestao complemento" data-sugestao-id={c.id} data-regra={c.regra}>
              <p className="sugestao-tipo">
                {c.descricao}
                <span className="sugestao-linhas">
                  {" "}
                  · {quantidadeParaTexto(c.quantidade)} {c.unidade}
                </span>
              </p>
              {c.estimativa_consumo && (
                <p>
                  <span className="selo-consumo" title="Quantidade estimada pela regra de consumo; não é preço">
                    Quantidade estimada
                  </span>
                </p>
              )}
              <p className="sugestao-texto">{c.motivo}</p>
              <p className="nota">
                Motivado {c.origem_linhas.length === 1 ? "pela linha" : "pelas linhas"} {c.origem_linhas.join(", ")}.
              </p>
              <div className="sugestao-acoes">
                <button
                  type="button"
                  className="botao-primario"
                  disabled={travado}
                  onClick={() => aceitarComplemento(c)}
                  aria-label={`Aceitar o complemento: ${c.descricao}`}
                >
                  Aceitar
                </button>
                <button
                  type="button"
                  className="botao-secundario"
                  onClick={() => recusar(c.id, c.descricao)}
                  aria-label={`Recusar o complemento: ${c.descricao}`}
                >
                  Recusar
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {aviso}
      </p>
    </>
  );
}
