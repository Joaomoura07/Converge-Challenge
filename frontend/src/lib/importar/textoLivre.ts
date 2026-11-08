// Lista em TEXTO LIVRE, um item por linha: o jeito de quem não tem planilha (lista do WhatsApp, bloco de notas,
// CSV com uma coluna só, texto colado). Formatos vistos no acervo (docs/arquivos-teste, listas do WhatsApp):
//   - 15 sacos 20 kg Argamassa colante AC-III      → 15 un, "Argamassa colante AC-III (saco 20 kg)"
//   - 3 lt 18 L Selador acrílico                   → 3 un,  "Selador acrílico (lata 18 L)"
//   - 2,80 m² Bancada em quartzo                   → 2,8 m2
//   - 5 Soleira em granito                         → 5 un
//   10 sacos de cimento · 2 m³ de areia · 2 milheiros de tijolo (→ 2000 un)
//   tinta branca 18 litros · porcelanato 60x60 - 30 m2 · Cimento (10 sc)
//   *PINTURA*  → categoria dos itens seguintes; "Obra: ...", "CEP ...", saudações → ignoradas
// Sem quantidade, a linha entra só com a descrição (a tela marca o campo para preencher). Nada é inventado.

import { normalizarUnidade } from "./csv";
import type { AvisoImportacao, ItemImportado } from "./tipos";

/** Palavra de embalagem → nome no singular. Vira "un" com a embalagem na descrição (a pesquisa converte). */
const EMBALAGENS: Record<string, string> = {
  saco: "saco", sacos: "saco", sc: "saco", scs: "saco",
  lata: "lata", latas: "lata", lt: "lata", lts: "lata",
  galao: "galão", galoes: "galão", gl: "galão",
  balde: "balde", baldes: "balde", barrica: "barrica", barricas: "barrica", barr: "barrica",
  caixa: "caixa", caixas: "caixa", cx: "caixa", cxs: "caixa",
  rolo: "rolo", rolos: "rolo", rl: "rolo",
  pacote: "pacote", pacotes: "pacote", pct: "pacote", pcts: "pacote",
  pote: "pote", potes: "pote", barra: "barra", barras: "barra", br: "barra",
  kit: "kit", kits: "kit", fardo: "fardo", fardos: "fardo", bisnaga: "bisnaga", bisnagas: "bisnaga",
  tubo: "tubo", tubos: "tubo", par: "par", pares: "par", painel: "painel", paineis: "painel", ch: "chapa", frasco: "frasco", frascos: "frasco", chapa: "chapa", chapas: "chapa",
};
/** Palavras de contagem: viram "un" sem nada na descrição. */
const CONTAGEM = new Set(["folha", "folhas", "peca", "pecas", "unidade", "unidades", "un", "und", "unid", "pc", "pcs", "x"]);
const MILHEIRO = new Set(["milheiro", "milheiros", "mil", "milh"]);

const semAcento = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Número escrito por brasileiro: "2,80" → 2.8; "1.500" → 1500; "12.5" → 12.5. */
export function numeroBr(s: string): number | null {
  const t = s.trim();
  if (!/^\d[\d.,]*$/.test(t)) return null;
  let n: string;
  if (t.includes(",") && t.includes(".")) n = t.replace(/\./g, "").replace(",", ".");
  else if (t.includes(",")) n = t.replace(",", ".");
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) n = t.replace(/\./g, "");
  else n = t;
  const v = Number(n);
  return Number.isFinite(v) && v > 0 ? v : null;
}

/** Unidade do contrato a partir de texto livre, inclusive por extenso ("metro quadrado", "quilos"). */
export function unidadeLivre(bruto: string): string | null {
  const t = semAcento(bruto).replace(/\.$/, "").trim();
  const extenso: Record<string, string> = {
    "metro quadrado": "m2", "metros quadrados": "m2", "m quadrado": "m2", "mq": "m2",
    "metro cubico": "m3", "metros cubicos": "m3", "m cubico": "m3",
    quilograma: "kg", quilogramas: "kg", kilo: "kg", kilos: "kg",
  };
  return extenso[t] ?? normalizarUnidade(bruto) ?? normalizarUnidade(t);
}

const RE_IGNORAR = /^(obra|cliente|endere[cç]o|cep|data|arquiteta?o?|respons[aá]vel|telefone|tel|fone|obs|observa[cç][aã]o|prazo|entrega)\b\s*:?/i;
const RE_CONVERSA = /^(oi|ol[aá]|bom dia|boa tarde|boa noite|obrigad|valeu|segue|seguem|abs|att|beleza|blz|ok|quantidades? j[aá])/i;
/** "[07/11/2026 10:21] Fulano: " ou "07/11/2026 10:21 - Fulano: " (exportação do WhatsApp). */
const RE_CARIMBO_WHATS = /^\[?\d{1,2}\/\d{1,2}\/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\]?\s*-?\s*[^:]{1,40}:\s*/;
const RE_MARCADOR = /^\s*(?:[-•*·▪►✓✔]|\d{1,3}[.)]\s|\(\d{1,3}\)\s)\s*/;
const NUM = String.raw`\d[\d.,]*`;
const RE_CONTEUDO = new RegExp(String.raw`^(${NUM})\s*(m²|m2|m³|m3|ml|l|lt|litros?|kg|g|m|metros?|un|unidades?|p[cç]s?|pe[cç]as?)(?=[\s.,;)]|$)\.?\s*`, "i");

export type LeituraLinha = { descricao: string; quantidade: number | null; unidade: string | null; embalagem: string | null; milheiro: boolean };

/** Lê uma linha "solta". null quando a linha não descreve material (vazia, conversa, título). */
export function lerLinhaLivre(original: string): LeituraLinha | null {
  let s = original.replace(RE_CARIMBO_WHATS, "").replace(RE_MARCADOR, "").replace(/\s+/g, " ").trim();
  s = s.replace(/^\*+|\*+$/g, "").trim();
  if (!s || RE_IGNORAR.test(s) || RE_CONVERSA.test(s)) return null;

  // 1) quantidade NO COMEÇO: "15 sacos 20 kg Argamassa", "2 m³ de areia", "5 Soleira", "x10 Cimento"
  const ini = s.match(new RegExp(String.raw`^(?:x\s*)?(${NUM})\s*(.*)$`, "i"));
  if (ini && ini[2] && /[a-zà-ú]/i.test(ini[2])) {
    const qtd = numeroBr(ini[1]);
    let resto = ini[2].trim();
    const [palavra = "", ...depois] = resto.split(" ");
    const p = semAcento(palavra).replace(/[.,:]$/, "");
    const posPalavra = depois.join(" ");
    if (qtd !== null) {
      // Embalagem de verdade: com conteúdo ("15 sacos 20 kg"), no plural, abreviada ("cx") ou em minúscula.
      // "4 Caixa sifonada" e "1 Caixa d'água" são NOMES de produto, não embalagem.
      const contAntes = posPalavra.match(RE_CONTEUDO);
      const ehEmbalagem = Boolean(EMBALAGENS[p]) && (contAntes !== null || /s$/.test(p) || p.length <= 4 || palavra[0] === palavra[0].toLowerCase());
      if (ehEmbalagem) {
        // "15 sacos 20 kg Argamassa": embalagem com conteúdo; "6 rolos Fita": só a embalagem
        const cont = contAntes;
        const emb = cont ? `${EMBALAGENS[p]} ${cont[1]} ${cont[2]}` : EMBALAGENS[p];
        const desc = (cont ? posPalavra.slice(cont[0].length) : posPalavra).replace(/^de\s+/i, "").trim();
        if (desc) return { descricao: `${desc} (${emb})`, quantidade: qtd, unidade: "un", embalagem: emb, milheiro: false };
      }
      if (MILHEIRO.has(p) && posPalavra) {
        return { descricao: posPalavra.replace(/^de\s+/i, "").trim(), quantidade: qtd * 1000, unidade: "un", embalagem: null, milheiro: true };
      }
      if (CONTAGEM.has(p) && posPalavra) {
        return { descricao: posPalavra.replace(/^de\s+/i, "").trim(), quantidade: qtd, unidade: "un", embalagem: null, milheiro: false };
      }
      // unidade de medida, inclusive por extenso de duas palavras ("metros quadrados de piso")
      const duas = `${palavra} ${depois[0] ?? ""}`.trim();
      const u2 = depois.length > 1 ? unidadeLivre(duas) : null;
      const u1 = unidadeLivre(palavra);
      if (u2 && depois.length > 1) {
        const desc = depois.slice(1).join(" ").replace(/^de\s+/i, "").trim();
        if (desc) return { descricao: desc, quantidade: qtd, unidade: u2, embalagem: null, milheiro: false };
      }
      if (u1 && posPalavra) {
        return { descricao: posPalavra.replace(/^de\s+/i, "").trim(), quantidade: qtd, unidade: u1, embalagem: null, milheiro: false };
      }
      // "5 Soleira em granito": número e o nome do material → contagem
      resto = resto.replace(/^de\s+/i, "");
      return { descricao: resto, quantidade: qtd, unidade: "un", embalagem: null, milheiro: false };
    }
  }

  // 2) quantidade NO FIM: "tinta branca 18 litros", "porcelanato 60x60 - 30 m2", "Cimento (10 sc)", "Areia: 2 m3"
  const fim = s.match(new RegExp(String.raw`^(.*?[a-zà-ú].*?)(?:\s+-\s+|\s*[:=]\s*|\s*\(\s*|\s+x\s*|\s+)(${NUM})\s*([a-zà-ú][a-zà-ú0-9²³ ]{0,19}?)?\s*\)?\s*$`, "i"));
  if (fim) {
    const qtd = numeroBr(fim[2]);
    const descricao = fim[1].replace(/[\s\-–:(]+$/, "").trim();
    const resto = semAcento(fim[3] ?? "").trim();
    if (qtd !== null && descricao) {
      if (!resto) return { descricao, quantidade: qtd, unidade: "un", embalagem: null, milheiro: false };
      if (EMBALAGENS[resto]) return { descricao: `${descricao} (${EMBALAGENS[resto]})`, quantidade: qtd, unidade: "un", embalagem: EMBALAGENS[resto], milheiro: false };
      if (MILHEIRO.has(resto)) return { descricao, quantidade: qtd * 1000, unidade: "un", embalagem: null, milheiro: true };
      if (CONTAGEM.has(resto)) return { descricao, quantidade: qtd, unidade: "un", embalagem: null, milheiro: false };
      const u = unidadeLivre(resto);
      if (u) return { descricao, quantidade: qtd, unidade: u, embalagem: null, milheiro: false };
    }
  }

  // 3) só o nome do material
  return { descricao: s, quantidade: null, unidade: null, embalagem: null, milheiro: false };
}

/** Título de seção: "*PINTURA*", "PINTURA:", "Pintura" sozinho em CAIXA ALTA. */
function secao(original: string): string | null {
  const s = original.replace(RE_CARIMBO_WHATS, "").trim();
  const negrito = s.match(/^\*+\s*([^*]{2,90}?)\s*\*+:?$/);
  if (negrito) return negrito[1].trim();
  const caixaAlta = s.match(/^([A-ZÀ-Ú][A-ZÀ-Ú\s/&]{2,40}):?$/);
  if (caixaAlta) return caixaAlta[1].trim();
  return null;
}

const capitalizar = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

/** Lê várias linhas. `linhaInicial` = número da 1ª linha no arquivo (para os avisos citarem a linha certa). */
export function lerListaTexto(linhas: string[], linhaInicial = 1): { itens: ItemImportado[]; avisos: AvisoImportacao[] } {
  const itens: ItemImportado[] = [];
  const avisos: AvisoImportacao[] = [];
  let categoria: string | null = null;
  // Lista só de nomes (nenhuma linha com número)? Então cada linha não vazia é um item. Senão, linha sem número
  // e sem cara de material (título, comentário) é ignorada e listada num aviso.
  const comNumero = linhas.filter((l) => /\d/.test(l)).length;
  const soNomes = comNumero === 0;
  const ignoradas: number[] = [];
  let primeiroTitulo = true;
  linhas.forEach((bruta, i) => {
    const linha = linhaInicial + i;
    if (!bruta.trim()) return;
    const sec = secao(bruta);
    if (sec && !soNomes) {
      // 1ª linha em negrito costuma ser o título da lista ("*Lista de compras – ...*"), não uma seção
      if (primeiroTitulo && itens.length === 0 && /lista|or[cç]amento|compras|obra/i.test(sec)) { primeiroTitulo = false; return; }
      categoria = capitalizar(sec);
      return;
    }
    const r = lerLinhaLivre(bruta);
    if (!r) { ignoradas.push(linha); return; }
    if (r.quantidade === null && !soNomes) {
      // linha de texto no meio de uma lista com quantidades: título ou comentário
      // frase de conversa ("Qualquer dúvida me chama. Pedir entrega pela manhã.") não é material
      const frase = /[.!?]\s+\S/.test(r.descricao) || (/\.$/.test(r.descricao) && r.descricao.split(" ").length >= 4);
      const recado = /\b(me chama|d[uú]vida|entrega|pedir|por favor|obrigad)/i.test(r.descricao);
      if (/^[^a-z]*$/i.test(r.descricao) || r.descricao.split(" ").length > 12 || /[!?👍]/u.test(r.descricao) || frase || recado) {
        ignoradas.push(linha);
        return;
      }
    }
    itens.push({ linha, categoria, descricao: r.descricao.slice(0, 300), quantidade: r.quantidade, unidade: r.unidade, nivel: null, extras: { texto_original: bruta.trim() } });
    if (r.embalagem) {
      avisos.push({ linha, codigo: "EMBALAGEM_COMO_UNIDADE", mensagem: `Linha ${linha}: ${r.quantidade} ${r.embalagem} virou ${r.quantidade} un (a embalagem foi para a descrição). Confira.` });
    }
    if (r.milheiro) {
      avisos.push({ linha, codigo: "EMBALAGEM_COMO_UNIDADE", mensagem: `Linha ${linha}: milheiro convertido em ${r.quantidade} unidades. Confira.` });
    }
    if (r.quantidade === null) {
      avisos.push({ linha, codigo: "QUANTIDADE_AUSENTE", mensagem: `A linha ${linha} está sem quantidade.` });
    }
  });
  if (ignoradas.length) {
    avisos.push({
      linha: ignoradas[0],
      codigo: "LISTA_TEXTO",
      mensagem: `${ignoradas.length === 1 ? "1 linha sem material foi ignorada" : `${ignoradas.length} linhas sem material (títulos, endereço, conversa) foram ignoradas`}: ${ignoradas.slice(0, 8).join(", ")}${ignoradas.length > 8 ? "…" : ""}.`,
    });
  }
  return { itens, avisos };
}
