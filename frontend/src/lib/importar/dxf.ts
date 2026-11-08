// Leitor de DXF (planta do AutoCAD) no navegador. Um DXF traz medidas, não a especificação do produto:
// cada layer/bloco vira uma linha com a medida que o arquivo realmente informa e a origem em `extras`.
//  - blocos (INSERT): contagem em `un`
//  - polilinhas fechadas: área em m2 (fórmula do polígono), somada por layer
//  - polilinhas abertas e linhas: comprimento em m, somado por layer
// Sem $INSUNITS não se sabe a escala: a linha entra SEM quantidade, com aviso. DWG é recusado com orientação.

import DxfParser from "dxf-parser";
import { mapearNome } from "./mapeamento-dxf";
import type { AvisoImportacao, ItemImportado, ResultadoImportacao } from "./tipos";

// $INSUNITS -> metros por unidade de desenho
const METROS: Record<number, number> = { 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1, 7: 1000 };

type P = { x: number; y: number };
type Grupo = { chave: string; nome: string; tipo: "bloco" | "area" | "comprimento"; valor: number; n: number; handles: string[] };

const area = (v: P[]) => Math.abs(v.reduce((s, p, i) => s + (p.x * v[(i + 1) % v.length].y - v[(i + 1) % v.length].x * p.y), 0)) / 2;
const comprimento = (v: P[], fechada: boolean) => {
  let s = 0;
  for (let i = 0; i < v.length - 1; i++) s += Math.hypot(v[i + 1].x - v[i].x, v[i + 1].y - v[i].y);
  if (fechada && v.length > 2) s += Math.hypot(v[0].x - v[v.length - 1].x, v[0].y - v[v.length - 1].y);
  return s;
};

export function importarDxf({ nome, bytes }: { nome: string; bytes: Uint8Array }): ResultadoImportacao {
  if (bytes.length === 0) return { erro: { codigo: "ARQUIVO_VAZIO", mensagem: "O arquivo está vazio." } };
  // DWG binário começa com "AC10": não é DXF.
  if (bytes.length > 6 && String.fromCharCode(...bytes.slice(0, 2)) === "AC") {
    return { erro: { codigo: "FORMATO_NAO_SUPORTADO", mensagem: "Este arquivo é um DWG. No AutoCAD use Salvar como e escolha DXF; depois envie o .dxf." } };
  }
  // DXF antigo (R12 a 2004) costuma estar em Windows-1252; os novos, em UTF-8.
  let texto: string;
  try {
    texto = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    texto = new TextDecoder("windows-1252").decode(bytes);
  }
  let dxf;
  try {
    dxf = new DxfParser().parseSync(texto);
  } catch {
    dxf = null;
  }
  if (!dxf || !dxf.entities) {
    return { erro: { codigo: "ARQUIVO_CORROMPIDO", mensagem: "Não consegui ler este DXF (arquivo corrompido ou não é DXF de texto)." } };
  }

  const insunits = Number((dxf.header as Record<string, unknown> | undefined)?.["$INSUNITS"] ?? 0);
  const metros = METROS[insunits] ?? null;
  const grupos = new Map<string, Grupo>();
  const somar = (chave: string, nomeG: string, tipo: Grupo["tipo"], valor: number, handle?: string) => {
    const g = grupos.get(chave) ?? { chave, nome: nomeG, tipo, valor: 0, n: 0, handles: [] };
    g.valor += valor;
    g.n += 1;
    if (handle && g.handles.length < 50) g.handles.push(handle);
    grupos.set(chave, g);
  };

  for (const e of dxf.entities as unknown as Array<Record<string, unknown>>) {
    const layer = String(e.layer ?? "0");
    const handle = e.handle != null ? String(e.handle) : undefined;
    if (e.type === "INSERT") {
      const bloco = String(e.name ?? layer);
      const cols = Math.max(1, Number(e.columnCount ?? 1) || 1);
      const lins = Math.max(1, Number(e.rowCount ?? 1) || 1);
      somar(`b:${layer}:${bloco}`, bloco, "bloco", cols * lins, handle); // INSERT em matriz conta todas as cópias
    } else if (e.type === "LWPOLYLINE" || e.type === "POLYLINE") {
      const v = (e.vertices as P[] | undefined) ?? [];
      if (v.length < 2) continue;
      const fechada = Boolean(e.shape) && v.length >= 3;
      if (fechada) somar(`a:${layer}`, layer, "area", area(v), handle);
      else somar(`c:${layer}`, layer, "comprimento", comprimento(v, false), handle);
    } else if (e.type === "LINE") {
      const v = (e.vertices as P[] | undefined) ?? [];
      if (v.length === 2) somar(`c:${layer}`, layer, "comprimento", comprimento(v, false), handle);
    }
  }

  if (grupos.size === 0) {
    return { origem: origem(nome, 0), itens: [], avisos: [{ linha: null, codigo: "SEM_DADOS", mensagem: "O DXF não tem blocos nem polilinhas para contar." }] };
  }

  const avisos: AvisoImportacao[] = [];
  const itens: ItemImportado[] = [];
  let linha = 0;
  for (const g of grupos.values()) {
    linha += 1;
    const m = mapearNome(g.nome);
    let quantidade: number | null;
    let unidade: string;
    if (g.tipo === "bloco") {
      quantidade = g.valor;
      unidade = "un";
    } else {
      unidade = g.tipo === "area" ? "m2" : "m";
      if (metros == null) {
        quantidade = null;
        avisos.push({ linha, codigo: "QUANTIDADE_AUSENTE", mensagem: `Layer "${g.nome}": o DXF não informa a unidade do desenho ($INSUNITS). Informe a medida.` });
      } else {
        const bruto = g.tipo === "area" ? g.valor * metros * metros : g.valor * metros;
        quantidade = Math.round(bruto * 100) / 100;
      }
    }
    if (!m.conhecido) avisos.push({ linha, codigo: "EXTRACAO_AMBIGUA", mensagem: `"${g.nome}": não sei que material é; descreva-o.` });
    itens.push({
      linha,
      categoria: m.categoria,
      descricao: g.tipo === "area" ? `${m.descricao} (área)` : g.tipo === "comprimento" ? `${m.descricao} (comprimento)` : m.descricao,
      quantidade,
      unidade,
      nivel: null,
      extras: { origem_dxf: { layer: g.chave.split(":")[1], elementos: g.n, handles: g.handles } },
    });
  }
  return { origem: origem(nome, itens.length), itens, avisos };
}

function origem(arquivo: string, n: number) {
  return { arquivo, formato: "dxf" as const, software: "desconhecido" as const, aba: null, delimitador: null, codificacao: "utf-8", linhas_lidas: n, linhas_descartadas: 0 };
}
