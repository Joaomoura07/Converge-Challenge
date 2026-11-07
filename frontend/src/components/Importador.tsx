"use client";

import { useId, useRef, useState } from "react";
import type { Linha } from "@/lib/lista";
import { importarCsv } from "@/lib/importar/csv";
import { EXEMPLOS, type Exemplo } from "@/lib/importar/exemplos";
import { importacaoParaLinhas, resumoAvisos } from "@/lib/importar/paraLinhas";
import { ehErro, LIMITE_BYTES, type Importacao } from "@/lib/importar/tipos";

type Props = {
  /** CSV ativo: mostra o seletor de arquivo; senão só os exemplos. */
  mostrarArquivo: boolean;
  /** quantas linhas já existem na lista (para perguntar acrescentar ou substituir) */
  linhasExistentes: number;
  novoId: () => string;
  onAplicar: (linhas: Linha[], como: "acrescentar" | "substituir") => void;
};

type Pendente = { importacao: Importacao; linhas: Linha[]; nome: string };
type Situacao =
  | { tipo: "livre" }
  | { tipo: "lendo"; nome: string }
  | { tipo: "erro"; mensagem: string; nome: string }
  | { tipo: "pronto"; resumo: string; avisos: string[] };

const ROTULO_CODIFICACAO: Record<string, string> = { "utf-8": "UTF-8", "windows-1252": "Windows-1252", "utf-16le": "UTF-16", "utf-16be": "UTF-16" };

export function Importador({ mostrarArquivo, linhasExistentes, novoId, onAplicar }: Props) {
  const [situacao, setSituacao] = useState<Situacao>({ tipo: "livre" });
  const [pendente, setPendente] = useState<Pendente | null>(null);
  const [exemplosAbertos, setExemplosAbertos] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);
  const idAviso = useId();

  /** Ponto único: arquivo enviado e exemplos passam por aqui, pelo mesmo leitor. */
  async function processar(nome: string, ler: () => Promise<Uint8Array>) {
    setPendente(null);
    setSituacao({ tipo: "lendo", nome });
    let bytes: Uint8Array;
    try {
      bytes = await ler();
    } catch {
      setSituacao({ tipo: "erro", nome, mensagem: "Não consegui abrir o arquivo. Tente de novo ou use o cadastro manual." });
      return;
    }
    if (bytes.length > LIMITE_BYTES) {
      setSituacao({ tipo: "erro", nome, mensagem: `O arquivo passa de ${LIMITE_BYTES / 1024 / 1024} MB. Divida a lista em partes.` });
      return;
    }
    const resultado = importarCsv({ nome, bytes });
    if (ehErro(resultado)) {
      // A lista atual NÃO é tocada: o trabalho já digitado continua lá.
      setSituacao({
        tipo: "erro",
        nome,
        mensagem: `${resultado.erro.mensagem} A lista atual foi mantida. Corrija o arquivo, exporte como CSV ou digite os materiais.`,
      });
      return;
    }
    if (resultado.itens.length === 0) {
      setSituacao({ tipo: "erro", nome, mensagem: "O arquivo tem cabeçalho, mas nenhuma linha de dados. A lista atual foi mantida." });
      return;
    }
    const linhas = importacaoParaLinhas(resultado, novoId);
    const resumo = montarResumo(resultado);
    const avisos = resumoAvisos(resultado).linhas;
    if (linhasExistentes > 0) {
      setPendente({ importacao: resultado, linhas, nome });
      setSituacao({ tipo: "pronto", resumo, avisos });
    } else {
      onAplicar(linhas, "substituir");
      setSituacao({ tipo: "pronto", resumo, avisos });
    }
  }

  function escolher(como: "acrescentar" | "substituir") {
    if (!pendente) return;
    onAplicar(pendente.linhas, como);
    setPendente(null);
  }

  async function aoEscolherArquivo(e: React.ChangeEvent<HTMLInputElement>) {
    const arquivo = e.target.files?.[0];
    // Permite escolher de novo o mesmo arquivo depois de corrigi-lo.
    e.target.value = "";
    if (!arquivo) return;
    if (arquivo.size > LIMITE_BYTES) {
      setPendente(null);
      setSituacao({ tipo: "erro", nome: arquivo.name, mensagem: `O arquivo passa de ${LIMITE_BYTES / 1024 / 1024} MB. Divida a lista em partes.` });
      return;
    }
    await processar(arquivo.name, async () => new Uint8Array(await arquivo.arrayBuffer()));
  }

  async function usarExemplo(ex: Exemplo) {
    setExemplosAbertos(false);
    await processar(`${ex.id}.csv`, async () => {
      const r = await fetch(ex.arquivo);
      if (!r.ok) throw new Error("exemplo indisponível");
      return new Uint8Array(await r.arrayBuffer());
    });
  }

  return (
    <div className="importador">
      <div className="importador-acoes">
        {mostrarArquivo && (
          <>
            <input
              ref={entrada}
              id="arquivo-csv"
              className="somente-leitor"
              type="file"
              accept=".csv,text/csv,text/plain"
              onChange={aoEscolherArquivo}
              aria-describedby={idAviso}
            />
            <button type="button" className="botao-primario" onClick={() => entrada.current?.click()}>
              Escolher arquivo CSV
            </button>
          </>
        )}
        <button
          type="button"
          className="botao-secundario"
          aria-expanded={exemplosAbertos}
          aria-controls="lista-exemplos"
          onClick={() => setExemplosAbertos((v) => !v)}
        >
          Usar arquivo de exemplo
        </button>
      </div>

      {exemplosAbertos && (
        <ul id="lista-exemplos" className="exemplos">
          {EXEMPLOS.map((ex) => (
            <li key={ex.id}>
              <button type="button" className="exemplo" onClick={() => usarExemplo(ex)}>
                <span className="exemplo-nome">{ex.rotulo}</span>
                <span className="nota">{ex.descricao}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <p id={idAviso} className="nota" role="status" aria-live="polite">
        {situacao.tipo === "livre" &&
          (mostrarArquivo
            ? "Aceita CSV de até 20 MB, em UTF-8 ou Windows-1252, com ponto e vírgula, vírgula ou tabulação. A lista só muda depois da leitura."
            : "Os exemplos usam o mesmo leitor dos arquivos enviados.")}
        {situacao.tipo === "lendo" && `Lendo ${situacao.nome}…`}
      </p>

      {situacao.tipo === "erro" && (
        <div className="aviso-erro" role="alert">
          <p className="aviso-titulo">Não foi possível importar {situacao.nome}</p>
          <p>{situacao.mensagem}</p>
          <button type="button" className="botao-link" onClick={() => setSituacao({ tipo: "livre" })}>
            Entendi
          </button>
        </div>
      )}

      {situacao.tipo === "pronto" && (
        <div className="aviso-ok" role="status">
          <p className="aviso-titulo">{situacao.resumo}</p>
          {situacao.avisos.length > 0 && (
            <details>
              <summary>
                {situacao.avisos.length} {situacao.avisos.length === 1 ? "ponto para conferir" : "pontos para conferir"}
              </summary>
              <ul className="lista-avisos">
                {situacao.avisos.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {pendente && (
        <div className="aviso-decisao" role="alertdialog" aria-labelledby="titulo-decisao">
          <p id="titulo-decisao" className="aviso-titulo">
            A lista já tem {linhasExistentes} {linhasExistentes === 1 ? "item" : "itens"}. O que fazer com os {pendente.linhas.length} de {pendente.nome}?
          </p>
          <div className="importador-acoes">
            <button type="button" className="botao-primario" onClick={() => escolher("acrescentar")}>
              Acrescentar à lista
            </button>
            <button type="button" className="botao-secundario" onClick={() => escolher("substituir")}>
              Substituir a lista
            </button>
            <button type="button" className="botao-link" onClick={() => setPendente(null)}>
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function montarResumo(r: Importacao): string {
  const cod = ROTULO_CODIFICACAO[r.origem.codificacao ?? ""] ?? r.origem.codificacao ?? "?";
  const sep = r.origem.delimitador === "\t" ? "tabulação" : r.origem.delimitador === ";" ? "ponto e vírgula" : r.origem.delimitador === "," ? "vírgula" : r.origem.delimitador;
  return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · ${cod} · separador: ${sep}`;
}
