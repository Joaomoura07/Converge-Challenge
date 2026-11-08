import { parseSkp, type Definition, type SkpModel } from "openskp";
import { LIMITE_DESCOMPACTADO, tamanhoDescompactado } from "./excel";
import { mapearNome } from "./mapeamento-dxf";
import { LIMITE_BYTES, LIMITE_ITENS, LIMITE_ITENS_ORCAMENTO, type AvisoImportacao, type ErroImportacao, type ItemImportado, type ResultadoImportacao } from "./tipos";

type Grupo = {
  descricao: string;
  definicao: Definition;
  contar: boolean;
  ocorrencias: number;
  referencias: string[];
};

const erro = (codigo: ErroImportacao["erro"]["codigo"], mensagem: string): ErroImportacao =>
  ({ erro: { codigo, mensagem } });

const grande = () => erro("ARQUIVO_GRANDE_DEMAIS", "O modelo SketchUp passou do limite de leitura. Divida o projeto em arquivos menores.");
const corrompido = () => erro("ARQUIVO_CORROMPIDO", "Não consegui ler o modelo SketchUp. Abra e salve uma nova cópia .skp ou exporte o quantitativo como CSV.");

/** Confere o ZIP embutido nos SKP modernos antes de descompactar. */
function validarContainer(bytes: Uint8Array): ErroImportacao | null {
  if (!bytes.length) return erro("ARQUIVO_VAZIO", "O arquivo está vazio.");
  if (bytes.length > LIMITE_BYTES) return grande();
  if (bytes[0] !== 255 || bytes[1] !== 254 || bytes[2] !== 255 || bytes[3] !== 14) {
    return erro("FORMATO_INVALIDO", "Este arquivo não tem o cabeçalho de um modelo SketchUp. Selecione um arquivo .skp.");
  }
  // A biblioteca também reconhece o contêiner MFC legado pelo marcador CVersionMap.
  const cabecalho = new TextDecoder("windows-1252").decode(bytes.subarray(0, 512));
  if (!cabecalho.slice(0, 256).includes("PK\x03\x04") && cabecalho.includes("CVersionMap")) return null;
  for (let i = 0; i + 3 < bytes.length; i++) {
    if (bytes[i] !== 80 || bytes[i + 1] !== 75 || bytes[i + 2] !== 3 || bytes[i + 3] !== 4) continue;
    const tamanho = tamanhoDescompactado(bytes.subarray(i));
    if (!tamanho) return corrompido();
    return tamanho.total > LIMITE_DESCOMPACTADO || tamanho.entradas > 5_000 ? grande() : null;
  }
  return corrompido();
}

const nomeUtil = (nome: string) => {
  const limpo = nome.trim();
  return /^(?:(?:group|grupo|component|componente)(?:\s*#?\d+)?|untitled|sem título)$/i.test(limpo) ? "" : limpo;
};
const pedeMedida = /\b(pisos?|floor|paredes?|walls?|lajes?|slabs?|forros?|ceilings?|revestimentos?|rodap[eé]s?|tubos?|tubula[cç][aã]o|pipes?)\b/i;

function montarLista(modelo: SkpModel, arquivo: string): ResultadoImportacao {
  const grupos = new Map<string, Grupo>();
  const camadasOcultas = new Set(modelo.layers.filter(c => c.hidden).map(c => c.name));
  let visitados = 0;
  let ignorados = 0;
  let referenciasInvalidas = 0;
  let excedeu = false;

  function visitar(def: Definition, caminho: Set<number>, nome: string, referencia?: string) {
    if (excedeu) return;
    // Só contamos componentes nomeados com geometria própria e sem subcomponentes.
    // Um conjunto com filhos é percorrido para não contar o conjunto e suas peças como o mesmo material.
    if (def.faces.length || def.edges.length) {
      const contar = Boolean(referencia && nome && !def.isGroup && !def.instances.length && !pedeMedida.test(nome));
      const descricao = (nome || (referencia ? "Componente sem nome" : "Geometria solta do modelo")).slice(0, 300);
      const chave = JSON.stringify([def.id, descricao, contar]);
      let grupo = grupos.get(chave);
      if (!grupo) {
        if (grupos.size >= LIMITE_ITENS_ORCAMENTO) { excedeu = true; return; }
        grupo = { descricao, definicao: def, contar, ocorrencias: 0, referencias: [] };
        grupos.set(chave, grupo);
      }
      grupo.ocorrencias++;
      if (referencia && grupo.referencias.length < 20) grupo.referencias.push(referencia);
    }
    for (const [indice, instancia] of def.instances.entries()) {
      if (++visitados > LIMITE_ITENS) { excedeu = true; return; }
      const filha = modelo.definitions.get(instancia.refIdx);
      if (!filha || caminho.has(filha.id)) { referenciasInvalidas++; continue; }
      if (instancia.hidden || camadasOcultas.has(instancia.layer) || filha.isImage) { ignorados++; continue; }
      if (caminho.size >= 64) { excedeu = true; return; }
      caminho.add(filha.id);
      const segmento = instancia.guid || `${def.id}:${indice + 1}`;
      const origem = referencia ? `${referencia}/${segmento}` : segmento;
      visitar(filha, caminho, nomeUtil(instancia.name) || nomeUtil(filha.name), origem);
      caminho.delete(filha.id);
      if (excedeu) return;
    }
  }

  visitar(modelo.root, new Set([modelo.root.id]), "");
  if (excedeu) return grande();
  if (referenciasInvalidas) return corrompido();

  const avisos: AvisoImportacao[] = [];
  const itens: ItemImportado[] = [...grupos.values()].map((g, indice) => {
    const linha = indice + 1;
    if (!g.contar) {
      avisos.push({ linha, codigo: "QUANTIDADE_AUSENTE", mensagem: "Confira o material e informe a quantidade e a unidade deste item." });
    }
    return {
      linha, descricao: g.descricao, categoria: mapearNome(g.descricao).categoria, nivel: null,
      quantidade: g.contar ? g.ocorrencias : null, unidade: g.contar ? "un" : null,
      extras: { origem_skp: { definicao: g.definicao.id, ocorrencias: g.ocorrencias, referencias: g.referencias } },
    };
  });
  if (!itens.length) avisos.push({ linha: null, codigo: "SEM_DADOS", mensagem: "O modelo não trouxe componentes ou geometria para a revisão." });
  if (itens.some(i => i.unidade === "un")) avisos.unshift({
    linha: null, codigo: "EXTRACAO_AMBIGUA",
    mensagem: "As quantidades em unidades são contagens de componentes do SketchUp. Confira se cada componente corresponde a um item de compra.",
  });
  return {
    origem: { arquivo, formato: "skp", software: "sketchup", aba: null, delimitador: null, codificacao: null,
      linhas_lidas: visitados, linhas_descartadas: ignorados },
    itens, avisos,
  };
}

export function importarSkp(nome: string, bytes: Uint8Array): ResultadoImportacao {
  const invalido = validarContainer(bytes);
  if (invalido) return invalido;
  try {
    const buffer = bytes.buffer instanceof ArrayBuffer && bytes.byteOffset === 0 && bytes.byteLength === bytes.buffer.byteLength
      ? bytes.buffer : new Uint8Array(bytes).buffer;
    return montarLista(parseSkp(buffer), nome);
  } catch {
    return corrompido();
  }
}
