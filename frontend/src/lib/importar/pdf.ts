// Leitor de PDF COM TEXTO da Fatia A (etapa 11), com PDF.js. Funções puras: recebem os bytes (e o módulo do PDF.js) e
// devolvem o MESMO contrato do CSV (Importacao) ou um erro com orientação. O PDF.js entra por parâmetro porque o
// navegador usa a build com worker e os testes (Node) usam a build "legacy" sem worker.
//
// O PDF não tem linhas e colunas: tem pedaços de texto com posição. Reconstruímos as linhas pelo `y` e as colunas pelo
// `x` do cabeçalho, conforme os dois layouts das amostras:
//  1. Tabela com cabeçalho ("Pedido de cotação": Item · Descrição · Embalagem · Qtd.);
//  2. Quadro de acabamentos (Ambiente × Piso/Parede/Teto), com a quantidade dentro da célula: "Portobello 90x90 (24,00 m²)".
// PDF escaneado (sem texto), protegido ou corrompido recebe orientação para CSV, Excel ou cadastro manual.

import { mapearRegistros, type Registro } from "./csv";
import { LIMITE_BYTES, type AvisoImportacao, type ErroImportacao, type ResultadoImportacao } from "./tipos";

export const LIMITE_PAGINAS = 30;

/** O pedaço do PDF.js que usamos (tipado à mão para não depender da build). */
export interface PdfjsMinimo {
  getDocument(src: Record<string, unknown>): {
    promise: Promise<{
      numPages: number;
      getPage(n: number): Promise<{ getTextContent(): Promise<{ items: unknown[] }> }>;
      destroy?(): Promise<void>;
    }>;
    destroy?(): Promise<void>;
  };
}

type Pedaco = { str: string; x: number; y: number; pagina: number };

const erro = (
  codigo: ErroImportacao["erro"]["codigo"],
  mensagem: string,
  extra: Partial<ErroImportacao["erro"]> = {},
): ErroImportacao => ({ erro: { codigo, mensagem, ...extra } });

const ORIENTACAO = "Exporte a lista como CSV ou Excel, ou digite os materiais.";

// ------------------------------------------------------------------ linhas e colunas

type Linha = { y: number; pagina: number; pedacos: Pedaco[] };

/** Agrupa os pedaços por página e por altura (`y` com tolerância: células da mesma linha variam ±1). */
function agruparLinhas(pedacos: Pedaco[]): Linha[] {
  const linhas: Linha[] = [];
  const ordenados = [...pedacos].sort((a, b) => a.pagina - b.pagina || b.y - a.y || a.x - b.x);
  for (const p of ordenados) {
    const ultima = linhas[linhas.length - 1];
    if (ultima && ultima.pagina === p.pagina && Math.abs(ultima.y - p.y) <= 3) ultima.pedacos.push(p);
    else linhas.push({ y: p.y, pagina: p.pagina, pedacos: [p] });
  }
  for (const l of linhas) l.pedacos.sort((a, b) => a.x - b.x);
  return linhas;
}

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const texto = (ps: Pedaco[]) => ps.map((p) => p.str.trim()).filter(Boolean).join(" ").replace(/\s+/g, " ").trim();

const EH_DESCRICAO = /^(descricao|material|produto|item de compra)$/;
const EH_QUANTIDADE = /^(qtd|qtde|quant|quantidade)$/;

type Cabecalho = { indiceLinha: number; colunas: { nome: string; x: number }[] };

/** Linha do cabeçalho de tabela: tem uma coluna de descrição e uma de quantidade. */
function acharCabecalhoTabela(linhas: Linha[]): Cabecalho | null {
  for (let i = 0; i < linhas.length; i++) {
    const celulas = linhas[i].pedacos.filter((p) => p.str.trim() !== "");
    const nomes = celulas.map((p) => norm(p.str));
    if (nomes.some((n) => EH_DESCRICAO.test(n)) && nomes.some((n) => EH_QUANTIDADE.test(n))) {
      return { indiceLinha: i, colunas: celulas.map((p) => ({ nome: p.str.trim(), x: p.x })) };
    }
  }
  return null;
}

const colunaDe = (colunas: { x: number }[], x: number): number => {
  let c = 0;
  for (let i = 0; i < colunas.length; i++) if (colunas[i].x <= x + 8) c = i;
  return c;
};

// ------------------------------------------------------------------ layout 1: tabela com cabeçalho

function lerTabela(linhas: Linha[], cab: Cabecalho, paginas: Map<number, number>): Registro[] {
  const nCol = cab.colunas.length;
  const iQtd = cab.colunas.findIndex((c) => EH_QUANTIDADE.test(norm(c.nome)));
  const iDesc = cab.colunas.findIndex((c) => EH_DESCRICAO.test(norm(c.nome)));
  const registros: Registro[] = [
    { linha: 1, celulas: cab.colunas.map((c) => c.nome), malformado: false },
  ];
  paginas.set(1, linhas[cab.indiceLinha].pagina);
  let n = 1;
  let ultimo: Registro | null = null;
  for (let i = cab.indiceLinha + 1; i < linhas.length; i++) {
    const celulas: string[] = Array.from({ length: nCol }, () => "");
    const porColuna: Pedaco[][] = Array.from({ length: nCol }, () => []);
    for (const p of linhas[i].pedacos) if (p.str.trim() !== "") porColuna[colunaDe(cab.colunas, p.x)].push(p);
    porColuna.forEach((ps, c) => (celulas[c] = texto(ps)));
    if (celulas.every((c) => c === "")) continue;
    // cabeçalho repetido no topo das páginas seguintes
    if (norm(celulas[iQtd]) === norm(cab.colunas[iQtd].nome) && norm(celulas[iDesc]) === norm(cab.colunas[iDesc].nome)) continue;
    const temQtd = celulas[iQtd] !== "";
    const temNumeroDeItem = celulas[0] !== "" && iDesc !== 0;
    const soDescricao = celulas.every((c, indice) => indice === iDesc || c === "");
    const anterior = linhas[i - 1];
    const continuacaoProxima = anterior.pagina === linhas[i].pagina && anterior.y - linhas[i].y <= 18;
    if (!temQtd && !temNumeroDeItem && soDescricao && continuacaoProxima && ultimo && celulas[iDesc] !== "") {
      // descrição que quebrou em duas linhas: continua a anterior
      ultimo.celulas[iDesc] = `${ultimo.celulas[iDesc]} ${celulas[iDesc]}`.trim();
      continue;
    }
    if (!temQtd && celulas[iDesc] === "") continue;
    n++;
    paginas.set(n, linhas[i].pagina);
    ultimo = { linha: n, celulas, malformado: false };
    registros.push(ultimo);
  }
  return registros;
}

// ------------------------------------------------------------------ layout 2: quadro de acabamentos

const RE_QTD_NA_CELULA = /^(.*?)\s*\(\s*(\d[\d.,]*)\s*(m²|m2|m³|m3|m|un|kg|l|cm|mm)\s*\)\s*$/i;

function acharCabecalhoQuadro(linhas: Linha[]): Cabecalho | null {
  for (let i = 0; i < linhas.length; i++) {
    const celulas = linhas[i].pedacos.filter((p) => p.str.trim() !== "");
    const nomes = celulas.map((p) => norm(p.str));
    if (nomes[0] === "ambiente" && nomes.length >= 3) {
      return { indiceLinha: i, colunas: celulas.map((p) => ({ nome: p.str.trim(), x: p.x })) };
    }
  }
  return null;
}

/** Só entra no quadro o texto que traz a quantidade na célula; o resto (carimbo da prancha, notas) é guardado em `ignorados`. */
function lerQuadro(linhas: Linha[], cab: Cabecalho, paginas: Map<number, number>, ignorados: string[]): Registro[] {
  const registros: Registro[] = [
    { linha: 1, celulas: ["Ambiente", "Categoria", "Descrição", "Quantidade", "Unidade"], malformado: false },
  ];
  paginas.set(1, linhas[cab.indiceLinha].pagina);
  let n = 1;
  let ambiente = "";
  for (let i = cab.indiceLinha + 1; i < linhas.length; i++) {
    const porColuna: Pedaco[][] = cab.colunas.map(() => []);
    for (const p of linhas[i].pedacos) porColuna[colunaDe(cab.colunas, p.x)].push(p);
    for (const [c, pedacos] of porColuna.entries()) {
      const s = texto(pedacos);
      if (s === "" || s === "—" || s === "-") continue;
      if (c === 0) {
        ambiente = s; // primeira coluna: nome do ambiente (vale para as linhas seguintes até o próximo)
        continue;
      }
      const m = s.match(RE_QTD_NA_CELULA);
      if (!m) {
        ignorados.push(s);
        continue;
      }
      n++;
      paginas.set(n, linhas[i].pagina);
      registros.push({ linha: n, celulas: [ambiente, cab.colunas[c].nome, m[1].trim(), m[2], m[3]], malformado: false });
    }
  }
  return registros;
}

// ------------------------------------------------------------------ importação

export async function importarPdf({
  nome,
  bytes,
  pdfjs,
}: {
  nome: string;
  bytes: Uint8Array;
  pdfjs: PdfjsMinimo;
}): Promise<ResultadoImportacao> {
  if (bytes.length === 0) return erro("ARQUIVO_VAZIO", "O arquivo está vazio.");
  if (bytes.length > LIMITE_BYTES) {
    return erro("ARQUIVO_GRANDE_DEMAIS", `O arquivo passa do limite de ${LIMITE_BYTES / 1024 / 1024} MB. Divida a lista em partes.`);
  }
  const cabecalhoPdf = String.fromCharCode(...bytes.subarray(0, Math.min(1024, bytes.length)));
  if (!cabecalhoPdf.includes("%PDF")) {
    return erro("FORMATO_INVALIDO", `O arquivo não é um PDF válido. ${ORIENTACAO}`);
  }

  let doc: Awaited<ReturnType<PdfjsMinimo["getDocument"]>["promise"]>;
  // cópia: o PDF.js pode transferir (e esvaziar) o buffer que recebe
  const tarefa = pdfjs.getDocument({ data: bytes.slice(), useWorkerFetch: false, isEvalSupported: false, disableFontFace: true, verbosity: 0 });
  try {
    doc = await tarefa.promise;
  } catch (e) {
    await tarefa.destroy?.().catch(() => undefined);
    const nomeErro = (e as { name?: string })?.name ?? "";
    if (nomeErro === "PasswordException") return erro("ARQUIVO_PROTEGIDO", `PDF protegido por senha. Remova a senha e exporte de novo. ${ORIENTACAO}`);
    return erro("ARQUIVO_CORROMPIDO", `Não foi possível ler o PDF; ele pode estar corrompido. ${ORIENTACAO}`);
  }

  try {
    if (doc.numPages > LIMITE_PAGINAS) {
      return erro("ARQUIVO_GRANDE_DEMAIS", `O PDF tem ${doc.numPages} páginas (o limite é ${LIMITE_PAGINAS}). Envie só as páginas da lista ou use CSV.`);
    }
    const pedacos: Pedaco[] = [];
    for (let p = 1; p <= doc.numPages; p++) {
      const pagina = await doc.getPage(p);
      const conteudo = await pagina.getTextContent();
      for (const it of conteudo.items as { str?: string; transform?: number[] }[]) {
        if (typeof it.str === "string" && it.transform) pedacos.push({ str: it.str, x: it.transform[4], y: it.transform[5], pagina: p });
      }
    }

    const caracteres = pedacos.reduce((s, p) => s + p.str.trim().length, 0);
    if (caracteres < 15) {
      return erro("PDF_SEM_TEXTO", `Este PDF parece ser uma imagem escaneada, sem texto para ler. ${ORIENTACAO}`);
    }

    const linhas = agruparLinhas(pedacos);
    const paginasPorLinha = new Map<number, number>();
    let registros: Registro[];
    let layout: "tabela" | "quadro";
    const ignorados: string[] = [];
    const tabela = acharCabecalhoTabela(linhas);
    const quadro = tabela ? null : acharCabecalhoQuadro(linhas);
    if (tabela) {
      registros = lerTabela(linhas, tabela, paginasPorLinha);
      layout = "tabela";
    } else if (quadro) {
      registros = lerQuadro(linhas, quadro, paginasPorLinha, ignorados);
      layout = "quadro";
    } else {
      return erro(
        "CABECALHO_NAO_ENCONTRADO",
        `Não reconheci uma tabela de materiais com descrição e quantidade neste PDF. ${ORIENTACAO}`,
      );
    }

    const avisos: AvisoImportacao[] = [];
    const r = mapearRegistros({ registros, avisos, nome, formato: "pdf", aba: null, delimitador: null, codificacao: null });
    if ("erro" in r) {
      return erro(r.erro.codigo, `${r.erro.mensagem} ${ORIENTACAO}`, { colunas_encontradas: r.erro.colunas_encontradas });
    }

    // Pedido de cotação: a quantidade é de EMBALAGENS. Cada quantidade vira unidades (un) da embalagem indicada,
    // que passa a fazer parte da descrição, e a pessoa é avisada para conferir.
    let usouEmbalagem = false;
    for (const item of r.itens) {
      item.extras.origem_pdf = { pagina: paginasPorLinha.get(item.linha), layout };
      const emb = typeof item.extras.Embalagem === "string" ? item.extras.Embalagem.trim() : "";
      if (emb && item.descricao) {
        item.descricao = `${item.descricao} (${emb})`;
        if (!item.unidade) item.unidade = "un";
        usouEmbalagem = true;
      }
    }
    if (usouEmbalagem) {
      r.avisos.unshift({
        linha: null,
        codigo: "EMBALAGEM_COMO_UNIDADE",
        mensagem:
          "Este pedido traz as quantidades em embalagens: cada quantidade foi lida como unidades (un) da embalagem indicada na descrição. Confira antes de enviar.",
      });
    }
    // Origem de cada aviso: a página do PDF.
    for (const a of r.avisos) {
      const pag = a.linha !== null ? paginasPorLinha.get(a.linha) : undefined;
      if (pag) a.mensagem = `${a.mensagem} (página ${pag})`;
    }
    if (ignorados.length > 0) {
      const exemplos = ignorados.slice(0, 3).map((t) => `"${t}"`).join(", ");
      r.avisos.push({
        linha: null,
        codigo: "EXTRACAO_AMBIGUA",
        mensagem: `${ignorados.length} ${ignorados.length === 1 ? "texto sem quantidade foi ignorado" : "textos sem quantidade foram ignorados"} (ex.: ${exemplos}). Se algum era material, acrescente à mão.`,
      });
    }
    r.avisos.push({
      linha: null,
      codigo: "EXTRACAO_AMBIGUA",
      mensagem: `Texto extraído de PDF (${layout === "tabela" ? "tabela com cabeçalho" : "quadro de acabamentos"}, ${doc.numPages} ${doc.numPages === 1 ? "página" : "páginas"}). Confira descrição, quantidade e unidade de cada linha.`,
    });
    return r;
  } catch {
    return erro("ARQUIVO_CORROMPIDO", `Não foi possível ler todas as páginas do PDF. ${ORIENTACAO}`);
  } finally {
    await (tarefa.destroy?.() ?? doc.destroy?.())?.catch(() => undefined);
  }
}
