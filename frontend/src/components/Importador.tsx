"use client";

import { useId, useRef, useState } from "react";
import type { Linha, ModoEntrada } from "@/lib/lista";
import { abasEscolhaveis, lerArquivo } from "@/lib/importar/arquivo";
import { EXEMPLOS, type Exemplo } from "@/lib/importar/exemplos";
import { importacaoParaLinhas, resumoAvisos } from "@/lib/importar/paraLinhas";
import { ehErro, LIMITE_BYTES, LIMITE_ITENS_ORCAMENTO, type Importacao } from "@/lib/importar/tipos";

type Props = {
  modo: ModoEntrada;
  /** quantas linhas já existem na lista (para perguntar acrescentar ou substituir) */
  linhasExistentes: number;
  novoId: () => string;
  onAplicar: (linhas: Linha[], como: "acrescentar" | "substituir") => void;
};

type Pendente = { importacao: Importacao; linhas: Linha[]; nome: string };
type EscolhaAba = { nome: string; bytes: Uint8Array; abas: string[]; selecionada: string };
type Situacao =
  | { tipo: "livre" }
  | { tipo: "lendo"; nome: string }
  | { tipo: "erro"; mensagem: string; nome: string }
  | { tipo: "pronto"; resumo: string; avisos: string[] };

const ROTULO_CODIFICACAO: Record<string, string> = { "utf-8": "UTF-8", "windows-1252": "Windows-1252", "utf-16le": "UTF-16", "utf-16be": "UTF-16" };

export function Importador({ modo, linhasExistentes, novoId, onAplicar }: Props) {
  const mostrarArquivo = modo !== "manual";
  const aceita = modo === "skp" ? ".skp" : modo === "ifc" ? ".ifc,.ifczip" : modo === "dxf" ? ".dxf,.dwg" : modo === "excel" ? ".xlsx,.xls,.xlsm" : modo === "revit" ? ".txt,text/plain" : modo === "pdf" ? ".pdf,application/pdf" : ".csv,text/csv";
  const [situacao, setSituacao] = useState<Situacao>({ tipo: "livre" });
  const [pendente, setPendente] = useState<Pendente | null>(null);
  const [escolhaAba, setEscolhaAba] = useState<EscolhaAba | null>(null);
  const [exemplosAbertos, setExemplosAbertos] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);
  const linhasAtuais = useRef(linhasExistentes);
  linhasAtuais.current = linhasExistentes;
  const idAviso = useId();

  /** Ponto único: arquivo enviado e exemplos passam por aqui, pelo mesmo leitor. */
  async function processar(nome: string, ler: () => Promise<Uint8Array>) {
    setPendente(null);
    setEscolhaAba(null);
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
    await avaliar(nome, bytes, null);
  }

  /** Lê os bytes com o leitor da extensão. Planilha com várias abas pede a escolha antes de mexer na lista. */
  async function avaliar(nome: string, bytes: Uint8Array, aba: string | null) {
    let resultado;
    try {
      resultado = await lerArquivo({ nome, bytes, aba });
    } catch {
      setSituacao({ tipo: "erro", nome, mensagem: "Não consegui carregar o leitor deste arquivo. Tente de novo. A lista atual foi mantida." });
      return;
    }
    if (!aba && !ehErro(resultado)) {
      const abas = abasEscolhaveis(resultado);
      if (abas.length > 1) {
        setEscolhaAba({ nome, bytes, abas: abas.map((a) => a.nome), selecionada: resultado.origem.aba ?? abas[0].nome });
        setSituacao({ tipo: "livre" });
        return;
      }
    }
    setEscolhaAba(null);
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
      setSituacao({ tipo: "erro", nome, mensagem: `${resultado.avisos[0]?.mensagem ?? "O arquivo não tem itens para importar."} A lista atual foi mantida.` });
      return;
    }
    if (resultado.itens.length > LIMITE_ITENS_ORCAMENTO) {
      setSituacao({
        tipo: "erro",
        nome,
        mensagem: `O arquivo tem ${resultado.itens.length.toLocaleString("pt-BR")} itens e um orçamento aceita até ${LIMITE_ITENS_ORCAMENTO.toLocaleString("pt-BR")}. Divida a lista em partes. A lista atual foi mantida.`,
      });
      return;
    }
    const linhas = importacaoParaLinhas(resultado, novoId);
    const resumo = montarResumo(resultado);
    const avisos = resumoAvisos(resultado).linhas;
    if (linhasAtuais.current > 0) {
      setPendente({ importacao: resultado, linhas, nome });
      setSituacao({ tipo: "pronto", resumo, avisos });
    } else {
      onAplicar(linhas, "substituir");
      setSituacao({ tipo: "pronto", resumo, avisos });
    }
  }

  function importarAba() {
    if (!escolhaAba) return;
    void avaliar(escolhaAba.nome, escolhaAba.bytes, escolhaAba.selecionada);
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
              accept={aceita}
              disabled={situacao.tipo === "lendo"}
              onChange={aoEscolherArquivo}
              aria-describedby={idAviso}
            />
            <button type="button" className="botao-primario" disabled={situacao.tipo === "lendo"} onClick={() => entrada.current?.click()}>
              {modo === "skp" ? "Escolher modelo SketchUp" : modo === "ifc" ? "Escolher modelo IFC" : modo === "dxf" ? "Escolher planta DXF" : modo === "excel" ? "Escolher planilha Excel" : modo === "revit" ? "Escolher TXT do Revit" : modo === "pdf" ? "Escolher PDF com texto" : "Escolher arquivo CSV"}
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
              <button type="button" className="exemplo" disabled={situacao.tipo === "lendo"} onClick={() => usarExemplo(ex)}>
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
            ? modo === "skp"
              ? "Aceita arquivos .skp de até 20 MB. O modelo é lido neste navegador. Confira os componentes e as medidas na revisão."
              : modo === "ifc"
              ? "Aceita o modelo exportado como .ifc (IFC2x3 ou IFC4) de até 20 MB. Exporte com as quantidades base ligadas para trazer as áreas. A lista só muda depois da leitura."
              : modo === "dxf"
              ? "Aceita planta .dxf de até 20 MB. DWG não é lido: salve como DXF no AutoCAD. A lista só muda depois da leitura."
              : modo === "pdf"
              ? "Aceita PDF com texto selecionável (pedido de cotação ou quadro de acabamentos) de até 20 MB e 30 páginas. PDF escaneado não tem texto para ler. A lista só muda depois da leitura."
              : modo === "revit"
              ? "Aceita a tabela exportada do Revit em .txt (colunas separadas por tabulação), de até 20 MB. A lista só muda depois da leitura."
              : modo === "excel"
              ? "Aceita .xlsx, .xls e .xlsm de até 20 MB. Macros nunca são executadas. A lista só muda depois da leitura."
              : "Aceita CSV de até 20 MB, em UTF-8 ou Windows-1252, com ponto e vírgula, vírgula ou tabulação. A lista só muda depois da leitura."
            : "Os exemplos usam o mesmo leitor dos arquivos enviados.")}
        {situacao.tipo === "lendo" && `Lendo ${situacao.nome}…`}
      </p>

      {escolhaAba && (
        <div className="aviso-decisao" role="group" aria-labelledby="titulo-aba">
          <p id="titulo-aba" className="aviso-titulo">
            {escolhaAba.nome} tem {escolhaAba.abas.length} abas com dados. Qual delas importar?
          </p>
          <div className="importador-acoes">
            <label className="importador-aba">
              <span className="nota">Aba</span>
              <select
                value={escolhaAba.selecionada}
                onChange={(e) => setEscolhaAba({ ...escolhaAba, selecionada: e.target.value })}
              >
                {escolhaAba.abas.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="botao-primario" onClick={importarAba}>
              Importar esta aba
            </button>
            <button type="button" className="botao-link" onClick={() => setEscolhaAba(null)}>
              Cancelar
            </button>
          </div>
        </div>
      )}

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
  if (r.origem.formato === "skp") {
    return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · modelo SketchUp`;
  }
  if (r.origem.formato === "ifc") {
    return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · modelo IFC (medidas do modelo; descreva os materiais)`;
  }
  if (r.origem.formato === "dxf") {
    return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · planta DXF (medidas do desenho; descreva os materiais)`;
  }
  if (r.origem.formato === "pdf") {
    return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · texto do PDF`;
  }
  if (r.origem.formato !== "csv" && r.origem.aba) {
    return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · aba "${r.origem.aba}"`;
  }
  const cod = ROTULO_CODIFICACAO[r.origem.codificacao ?? ""] ?? r.origem.codificacao ?? "?";
  const sep = r.origem.delimitador === "\t" ? "tabulação" : r.origem.delimitador === ";" ? "ponto e vírgula" : r.origem.delimitador === "," ? "vírgula" : r.origem.delimitador;
  return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · ${cod} · separador: ${sep}`;
}
