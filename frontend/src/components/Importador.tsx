"use client";

import { useId, useRef, useState } from "react";
import type { Linha } from "@/lib/lista";
import { abasEscolhaveis, lerArquivo } from "@/lib/importar/arquivo";
import { EXEMPLOS, type Exemplo } from "@/lib/importar/exemplos";
import { importacaoParaLinhas, resumoAvisos } from "@/lib/importar/paraLinhas";
import { ehErro, LIMITE_BYTES, LIMITE_ITENS_ORCAMENTO, type Importacao } from "@/lib/importar/tipos";

type Props = {
  /** Qual aba de entrada está ativa: CSV e Excel mostram o seletor de arquivo; as demais só os exemplos. */
  modo: "manual" | "csv" | "excel" | "revit" | "pdf" | "dxf" | "ifc";
  /** quantas linhas já existem na lista (para perguntar acrescentar ou substituir) */
  linhasExistentes: number;
  novoId: () => string;
  onAplicar: (linhas: Linha[], como: "acrescentar" | "substituir") => void;
  /** Esconde "Usar arquivo de exemplo" (na /demo o jurado baixa e arrasta o arquivo, como um arquiteto). */
  semExemplos?: boolean;
  /** Avisado quando um arquivo é solto, para a aba acompanhar a extensão (o leitor já escolhe pela extensão). */
  onArquivoSolto?: (nome: string) => void;
};

type Pendente = { importacao: Importacao; linhas: Linha[]; nome: string };
type EscolhaAba = { nome: string; bytes: Uint8Array; abas: string[]; selecionada: string };
type Situacao =
  | { tipo: "livre" }
  | { tipo: "lendo"; nome: string }
  | { tipo: "erro"; mensagem: string; nome: string }
  | { tipo: "pronto"; resumo: string; avisos: string[] };

const ROTULO_CODIFICACAO: Record<string, string> = { "utf-8": "UTF-8", "windows-1252": "Windows-1252", "utf-16le": "UTF-16", "utf-16be": "UTF-16" };

export function Importador({ modo, linhasExistentes, novoId, onAplicar, semExemplos, onArquivoSolto }: Props) {
  const mostrarArquivo = modo === "csv" || modo === "excel" || modo === "revit" || modo === "pdf" || modo === "dxf" || modo === "ifc";
  const aceita = modo === "ifc" ? ".ifc,.ifczip" : modo === "dxf" ? ".dxf,.dwg" : modo === "excel" ? ".xlsx,.xls,.xlsm" : modo === "revit" ? ".txt,text/plain" : modo === "pdf" ? ".pdf,application/pdf" : ".csv,text/csv";
  const [situacao, setSituacao] = useState<Situacao>({ tipo: "livre" });
  const [pendente, setPendente] = useState<Pendente | null>(null);
  const [escolhaAba, setEscolhaAba] = useState<EscolhaAba | null>(null);
  const [exemplosAbertos, setExemplosAbertos] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const [colado, setColado] = useState("");
  const idColar = useId();
  const entrada = useRef<HTMLInputElement>(null);
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
    // texto colado não tem extensão: vai para o leitor de .txt (tabela por tabulação ou lista, um item por linha)
    const resultado = await lerArquivo({ nome: nome === "lista colada" ? "lista-colada.txt" : nome, bytes, aba });
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
        mensagem: /Cadastro manual/.test(resultado.erro.mensagem)
          ? `${resultado.erro.mensagem} A lista atual foi mantida.`
          : `${resultado.erro.mensagem} A lista atual foi mantida. Se preferir, cole a lista na aba Cadastro manual, um material por linha.`,
      });
      return;
    }
    if (resultado.itens.length === 0) {
      setSituacao({ tipo: "erro", nome, mensagem: "O arquivo tem cabeçalho, mas nenhuma linha de dados. A lista atual foi mantida." });
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
    if (linhasExistentes > 0) {
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
    await receberArquivo(arquivo);
  }

  /** Arrastar e soltar: o mesmo caminho do botão (mesmo leitor, mesmos limites, mesma pergunta acrescentar/substituir). */
  async function aoSoltar(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setArrastando(false);
    const arquivo = e.dataTransfer.files?.[0];
    if (!arquivo) return;
    onArquivoSolto?.(arquivo.name);
    await receberArquivo(arquivo);
  }

  async function receberArquivo(arquivo: File) {
    if (arquivo.size > LIMITE_BYTES) {
      setPendente(null);
      setSituacao({ tipo: "erro", nome: arquivo.name, mensagem: `O arquivo passa de ${LIMITE_BYTES / 1024 / 1024} MB. Divida a lista em partes.` });
      return;
    }
    await processar(arquivo.name, async () => new Uint8Array(await arquivo.arrayBuffer()));
  }

  /** Lista colada (WhatsApp, bloco de notas, células copiadas do Excel): o mesmo leitor do .txt. Texto solto vira
   * um material por linha; células do Excel chegam separadas por tabulação e são lidas como tabela. */
  async function lerColado() {
    const texto = colado.trim();
    if (!texto) return;
    await processar("lista colada", async () => new TextEncoder().encode(texto));
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
    <div
      className={`importador${arrastando ? " importador--arrastando" : ""}`}
      onDragOver={(e) => {
        if (!Array.from(e.dataTransfer.types).includes("Files")) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        if (!arrastando) setArrastando(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastando(false);
      }}
      onDrop={aoSoltar}
    >
      <p className="importador-soltar" aria-hidden="true">
        {arrastando ? "Solte para ler a lista" : "Arraste o arquivo para cá ou escolha abaixo"}
      </p>
      <div className="importador-acoes">
        {mostrarArquivo && (
          <>
            <input
              ref={entrada}
              id="arquivo-csv"
              className="somente-leitor"
              type="file"
              accept={aceita}
              onChange={aoEscolherArquivo}
              aria-describedby={idAviso}
            />
            <button type="button" className="botao-primario" onClick={() => entrada.current?.click()}>
              {modo === "ifc" ? "Escolher modelo IFC" : modo === "dxf" ? "Escolher planta DXF" : modo === "excel" ? "Escolher planilha Excel" : modo === "revit" ? "Escolher TXT do Revit" : modo === "pdf" ? "Escolher PDF com texto" : "Escolher arquivo CSV"}
            </button>
          </>
        )}
        {!semExemplos && (
        <button
          type="button"
          className="botao-secundario"
          aria-expanded={exemplosAbertos}
          aria-controls="lista-exemplos"
          onClick={() => setExemplosAbertos((v) => !v)}
        >
          Usar arquivo de exemplo
        </button>
        )}
      </div>

      {modo === "manual" && (
        <div className="importador-colar">
          <label htmlFor={idColar} className="importador-colar__rotulo">
            Já tem a lista pronta? Cole aqui, um material por linha
          </label>
          <textarea
            id={idColar}
            rows={5}
            value={colado}
            onChange={(e) => setColado(e.target.value)}
            placeholder={"10 sacos de cimento\n2 m³ de areia\n15 caixas de porcelanato 60x60\ntinta acrílica branca 18 litros"}
          />
          <p className="nota">
            Serve a lista do WhatsApp, do bloco de notas ou células copiadas do Excel. Nada muda na tabela até você
            clicar em &quot;Ler a lista&quot;.
          </p>
          <div className="importador-acoes">
            <button type="button" className="botao-primario" onClick={() => void lerColado()} disabled={!colado.trim()}>
              Ler a lista
            </button>
          </div>
        </div>
      )}

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
            ? modo === "ifc"
              ? "Aceita o modelo exportado como .ifc (IFC2x3 ou IFC4) de até 20 MB. Exporte com as quantidades base ligadas para trazer as áreas. A lista só muda depois da leitura."
              : modo === "dxf"
              ? "Aceita planta .dxf de até 20 MB. DWG não é lido: salve como DXF no AutoCAD. A lista só muda depois da leitura."
              : modo === "pdf"
              ? "Aceita PDF com texto selecionável (pedido de cotação ou quadro de acabamentos) de até 20 MB e 30 páginas. PDF escaneado não tem texto para ler. A lista só muda depois da leitura."
              : modo === "revit"
              ? "Aceita a tabela exportada do Revit em .txt (colunas separadas por tabulação), de até 20 MB. A lista só muda depois da leitura."
              : modo === "excel"
              ? "Aceita .xlsx, .xls e .xlsm de até 20 MB. Não precisa de modelo: basta uma coluna com o material e outra com a quantidade (com ou sem cabeçalho). Macros nunca são executadas. A lista só muda depois da leitura."
              : "Aceita CSV de até 20 MB. Não precisa de modelo: basta uma coluna com o material e outra com a quantidade (com ou sem cabeçalho), ou um material por linha. A lista só muda depois da leitura."
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
  // Lista colada ou lida como texto (um material por linha): sem detalhe técnico de codificação e separador.
  const comoLista = r.avisos.some((a) => a.codigo === "LISTA_TEXTO");
  const fonte = r.origem.arquivo === "lista-colada.txt" ? "da lista colada" : `de ${r.origem.arquivo}`;
  if (comoLista || r.origem.arquivo === "lista-colada.txt") {
    return `${r.itens.length} ${r.itens.length === 1 ? "material lido" : "materiais lidos"} ${fonte}, um por linha`;
  }
  if (r.avisos.some((a) => a.codigo === "SEM_CABECALHO")) {
    return `${r.itens.length} ${r.itens.length === 1 ? "material lido" : "materiais lidos"} de ${r.origem.arquivo} (sem cabeçalho: confira as colunas)`;
  }
  const cod = ROTULO_CODIFICACAO[r.origem.codificacao ?? ""] ?? r.origem.codificacao ?? "?";
  const sep = r.origem.delimitador === "\t" ? "tabulação" : r.origem.delimitador === ";" ? "ponto e vírgula" : r.origem.delimitador === "," ? "vírgula" : r.origem.delimitador;
  return `${r.itens.length} ${r.itens.length === 1 ? "item lido" : "itens lidos"} de ${r.origem.arquivo} · ${cod} · separador: ${sep}`;
}
