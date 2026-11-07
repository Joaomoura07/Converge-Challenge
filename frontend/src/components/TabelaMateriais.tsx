"use client";

import type { Dispatch } from "react";
import {
  chaveToque,
  type Acao,
  type Campo,
  type ErrosLinha,
  type EstadoLista,
} from "@/lib/lista";
import { UNIDADES } from "@/lib/validacao";

type Props = {
  estado: EstadoLista;
  erros: Record<string, ErrosLinha>;
  despachar: Dispatch<Acao>;
  novoId: () => string;
};

export function idCampo(id: string, campo: Campo): string {
  return `campo-${id}-${campo}`;
}

export function TabelaMateriais({ estado, erros, despachar, novoId }: Props) {
  const { linhas, tocados } = estado;

  function adicionar() {
    const id = novoId();
    despachar({ tipo: "adicionar", id });
    // Foco na descrição da linha nova, depois que o React desenhar a linha.
    requestAnimationFrame(() => document.getElementById(idCampo(id, "descricao"))?.focus());
  }

  function remover(id: string, posicao: number) {
    despachar({ tipo: "remover", id });
    // Mantém o foco perto de onde o usuário estava.
    const vizinho = linhas[posicao + 1] ?? linhas[posicao - 1];
    requestAnimationFrame(() => {
      const alvo = vizinho ? document.getElementById(idCampo(vizinho.id, "descricao")) : document.getElementById("adicionar-linha");
      alvo?.focus();
    });
  }

  const mostrar = (id: string, campo: "descricao" | "quantidade" | "unidade") =>
    tocados[chaveToque(id, campo)] ? erros[id]?.[campo] : undefined;

  return (
    <div className="tabela" role="group" aria-label="Materiais da obra">
      <datalist id="unidades-validas">
        {UNIDADES.map((u) => (
          <option key={u} value={u} />
        ))}
      </datalist>

      {linhas.length === 0 ? (
        <div className="vazio">
          <p className="vazio-titulo">Nenhum material ainda</p>
          <p className="apoio">Adicione o primeiro item da obra. Cada linha precisa de descrição, quantidade e unidade.</p>
          <button id="adicionar-linha" type="button" className="botao-primario" onClick={adicionar}>
            Adicionar primeiro material
          </button>
        </div>
      ) : (
        <>
          <div className="linha cabecalho" aria-hidden="true">
            <span className="col-n">#</span>
            <span>Descrição</span>
            <span>Quantidade</span>
            <span>Unidade</span>
            <span>Categoria (opcional)</span>
            <span />
          </div>
          <ol className="linhas">
            {linhas.map((l, i) => {
              const eD = mostrar(l.id, "descricao");
              const eQ = mostrar(l.id, "quantidade");
              const eU = mostrar(l.id, "unidade");
              const temErro = Boolean(eD || eQ || eU);
              return (
                <li key={l.id} className={`linha${temErro ? " com-erro" : ""}`} data-linha-id={l.id}>
                  <span className="col-n" aria-hidden="true">
                    {i + 1}
                  </span>

                  <div className="celula">
                    <label htmlFor={idCampo(l.id, "descricao")} className="rotulo-movel">
                      Descrição
                    </label>
                    <input
                      id={idCampo(l.id, "descricao")}
                      aria-label={`Descrição do material ${i + 1}`}
                      value={l.descricao}
                      onChange={(e) => despachar({ tipo: "editar", id: l.id, campo: "descricao", valor: e.target.value })}
                      onBlur={() => despachar({ tipo: "tocar", id: l.id, campo: "descricao" })}
                      aria-invalid={Boolean(eD)}
                      aria-describedby={eD ? `erro-${l.id}-descricao` : undefined}
                      placeholder="Porcelanato 60x60 Portobello"
                      autoComplete="off"
                    />
                  </div>

                  <div className="celula">
                    <label htmlFor={idCampo(l.id, "quantidade")} className="rotulo-movel">
                      Quantidade
                    </label>
                    <input
                      id={idCampo(l.id, "quantidade")}
                      aria-label={`Quantidade do material ${i + 1}`}
                      value={l.quantidade}
                      onChange={(e) => despachar({ tipo: "editar", id: l.id, campo: "quantidade", valor: e.target.value })}
                      onBlur={() => despachar({ tipo: "tocar", id: l.id, campo: "quantidade" })}
                      inputMode="decimal"
                      aria-invalid={Boolean(eQ)}
                      aria-describedby={eQ ? `erro-${l.id}-quantidade` : undefined}
                      placeholder="12,5"
                      autoComplete="off"
                    />
                  </div>

                  <div className="celula">
                    <label htmlFor={idCampo(l.id, "unidade")} className="rotulo-movel">
                      Unidade
                    </label>
                    <input
                      id={idCampo(l.id, "unidade")}
                      aria-label={`Unidade do material ${i + 1}`}
                      list="unidades-validas"
                      value={l.unidade}
                      onChange={(e) => despachar({ tipo: "editar", id: l.id, campo: "unidade", valor: e.target.value })}
                      onBlur={() => despachar({ tipo: "tocar", id: l.id, campo: "unidade" })}
                      aria-invalid={Boolean(eU)}
                      aria-describedby={eU ? `erro-${l.id}-unidade` : undefined}
                      placeholder="m2"
                      autoComplete="off"
                    />
                  </div>

                  <div className="celula">
                    <label htmlFor={idCampo(l.id, "categoria")} className="rotulo-movel">
                      Categoria (opcional)
                    </label>
                    <input
                      id={idCampo(l.id, "categoria")}
                      aria-label={`Categoria do material ${i + 1}`}
                      value={l.categoria}
                      onChange={(e) => despachar({ tipo: "editar", id: l.id, campo: "categoria", valor: e.target.value })}
                      placeholder="Pintura"
                      autoComplete="off"
                    />
                  </div>

                  <div className="erros-linha">

                    {eD && (

                      <span id={`erro-${l.id}-descricao`} className="erro">

                        Descrição: {eD}

                      </span>

                    )}

                    {eQ && (

                      <span id={`erro-${l.id}-quantidade`} className="erro">

                        Quantidade: {eQ}

                      </span>

                    )}

                    {eU && (

                      <span id={`erro-${l.id}-unidade`} className="erro">

                        Unidade: {eU}

                      </span>

                    )}

                  </div>

                  {l.sugerida && (
                    <div className="sugerida-linha" data-sugerida={l.sugerida.regra}>
                      <span className="selo-sugerido">Sugerido · aceito por você</span>
                      {l.sugerida.estimativaConsumo && (
                        <span className="selo-consumo" title="Quantidade estimada pela regra de consumo; não é preço">
                          Quantidade estimada
                        </span>
                      )}
                      <span className="nota">
                        {l.sugerida.motivo} (linha{l.sugerida.origemLinhas.length === 1 ? "" : "s"} de origem:{" "}
                        {l.sugerida.origemLinhas.join(", ")})
                      </span>
                    </div>
                  )}

                  <button

                    type="button"

                    className="botao-remover"
                    onClick={() => remover(l.id, i)}
                    aria-label={`Remover material ${i + 1}`}
                  >
                    Remover
                  </button>
                </li>
              );
            })}
          </ol>
          <div className="acoes">
            <button id="adicionar-linha" type="button" className="botao-secundario" onClick={adicionar}>
              + Adicionar material
            </button>
          </div>
        </>
      )}
    </div>
  );
}
