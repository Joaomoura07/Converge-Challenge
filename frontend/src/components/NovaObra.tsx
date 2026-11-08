"use client";

import { useState } from "react";
import {
  formatarCep,
  validarCep,
  validarNomeObra,
  validarReais,
} from "@/lib/validacao";

export type Obra = {
  nome: string;
  cep: string; // texto, 8 dígitos
  orcamentoCliente: number; // reais
};

export type RascunhoObra = { nome: string; cep: string; orcamento: string };

type Props = {
  rascunho: RascunhoObra;
  onRascunho: (r: RascunhoObra) => void;
  onIniciar: (obra: Obra) => void;
  editando: boolean;
};

type Erros = Partial<Record<keyof RascunhoObra, string>>;

export function NovaObra({ rascunho, onRascunho, onIniciar, editando }: Props) {
  const [erros, setErros] = useState<Erros>({});

  function validar(): { obra?: Obra; erros: Erros } {
    const e: Erros = {};
    const nome = validarNomeObra(rascunho.nome);
    const cep = validarCep(rascunho.cep);
    const valor = validarReais(rascunho.orcamento);
    if (!nome.ok) e.nome = nome.erro;
    if (!cep.ok) e.cep = cep.erro;
    if (!valor.ok) e.orcamento = valor.erro;
    if (nome.ok && cep.ok && valor.ok) {
      return { erros: e, obra: { nome: nome.valor, cep: cep.valor, orcamentoCliente: valor.valor } };
    }
    return { erros: e };
  }

  function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    const { obra, erros: e } = validar();
    setErros(e);
    if (obra) {
      onIniciar(obra);
      return;
    }
    const primeiro = (["nome", "cep", "orcamento"] as const).find((c) => e[c]);
    if (primeiro) document.getElementById(`obra-${primeiro}`)?.focus();
  }

  function mudar(campo: keyof RascunhoObra, valor: string) {
    onRascunho({ ...rascunho, [campo]: valor });
    if (erros[campo]) setErros({ ...erros, [campo]: undefined });
  }

  return (
    <form className="folha" onSubmit={enviar} noValidate aria-labelledby="titulo-obra">
      <p className="secao-etiqueta">1 · Nova obra</p>
      <h2 id="titulo-obra" className="titulo-secao">
        {editando ? "Dados da obra" : "Comece pela obra"}
      </h2>
      <p className="apoio">O CEP da obra define a cidade da busca; o orçamento do cliente serve de teto para a viabilidade.</p>

      <div className="campos-obra">
        <div className="campo campo-nome">
          <label htmlFor="obra-nome">Nome da obra</label>
          <input
            id="obra-nome"
            value={rascunho.nome}
            onChange={(e) => mudar("nome", e.target.value)}
            aria-invalid={Boolean(erros.nome)}
            aria-describedby={erros.nome ? "erro-obra-nome" : undefined}
            autoComplete="off"
            placeholder="Reforma Apto Boa Viagem"
          />
          {erros.nome && (
            <p id="erro-obra-nome" className="erro" role="alert">
              {erros.nome}
            </p>
          )}
        </div>

        <div className="campo">
          <label htmlFor="obra-cep">CEP da obra</label>
          <input
            id="obra-cep"
            value={rascunho.cep}
            onChange={(e) => mudar("cep", e.target.value)}
            onBlur={() => {
              if (rascunho.cep === "") return;
              const r = validarCep(rascunho.cep);
              if (r.ok) onRascunho({ ...rascunho, cep: formatarCep(r.valor) });
            }}
            inputMode="numeric"
            autoComplete="postal-code"
            aria-invalid={Boolean(erros.cep)}
            aria-describedby={erros.cep ? "erro-obra-cep" : undefined}
            placeholder="51020-000"
          />
          {erros.cep && (
            <p id="erro-obra-cep" className="erro" role="alert">
              {erros.cep}
            </p>
          )}
        </div>

        <div className="campo">
          <label htmlFor="obra-orcamento">Orçamento do cliente (R$)</label>
          <input
            id="obra-orcamento"
            value={rascunho.orcamento}
            onChange={(e) => mudar("orcamento", e.target.value)}
            inputMode="decimal"
            aria-invalid={Boolean(erros.orcamento)}
            aria-describedby={erros.orcamento ? "erro-obra-orcamento" : undefined}
            placeholder="20.000,00"
          />
          {erros.orcamento && (
            <p id="erro-obra-orcamento" className="erro" role="alert">
              {erros.orcamento}
            </p>
          )}
        </div>
      </div>

      <div className="acoes">
        <button type="submit" className="botao-primario">
          {editando ? "Salvar dados da obra" : "Iniciar obra"}
        </button>
      </div>
    </form>
  );
}
