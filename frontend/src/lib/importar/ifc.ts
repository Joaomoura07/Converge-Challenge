// Leitor de IFC (modelo BIM exportado do Revit, ArchiCAD etc.) no navegador, sem dependência.
// IFC é texto no formato STEP (ISO 10303-21): uma linha por entidade, "#12=IFCDOOR('guid',$,'Porta 80',...);".
// O modelo traz MEDIDAS e nomes, quase nunca a especificação do produto (marca, cor, linha). Por isso:
//  - cada ambiente (IfcSpace) vira "Piso <ambiente> (área)" com a área declarada (NetFloorArea);
//  - paredes, lajes e revestimentos viram "<nome> (área)" com a área declarada;
//  - portas, janelas, louças, luminárias e mobiliário viram contagem em `un`, agrupados por nome e pavimento;
//  - o que deveria ter área e não tem quantidade declarada entra SEM quantidade, com aviso (nada é inventado);
//  - a origem (classe e GlobalIds) vai em `extras`.
// Quantidades calculadas da geometria ficam fora: só valem as declaradas em IfcElementQuantity.

import type { AvisoImportacao, ItemImportado, ResultadoImportacao } from "./tipos";

type Valor = string | number | null | Ref | Enum | Valor[] | Tipado;
type Ref = { ref: number };
type Enum = { enum: string };
type Tipado = { tipo: string; valor: Valor };
type Entidade = { id: number; tipo: string; args: Valor[] };

const ehRef = (v: Valor): v is Ref => typeof v === "object" && v !== null && "ref" in v;
const ehEnum = (v: Valor): v is Enum => typeof v === "object" && v !== null && "enum" in v;

// ---------- texto STEP ----------

/** Decodifica as sequências de escape do STEP: \X2\00E9\X0\ (UTF-16), \X\E9 (Latin-1), \S\ (Latin-1 alto). */
export function decodificarStep(s: string): string {
  return s
    .replace(/\\X2\\([0-9A-F]+)\\X0\\/gi, (_, hex: string) => {
      let r = "";
      for (let i = 0; i + 4 <= hex.length; i += 4) r += String.fromCharCode(parseInt(hex.slice(i, i + 4), 16));
      return r;
    })
    .replace(/\\X4\\([0-9A-F]+)\\X0\\/gi, (_, hex: string) => {
      let r = "";
      for (let i = 0; i + 8 <= hex.length; i += 8) r += String.fromCodePoint(parseInt(hex.slice(i, i + 8), 16));
      return r;
    })
    .replace(/\\X\\([0-9A-F]{2})/gi, (_, h: string) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\S\\(.)/g, (_, c: string) => String.fromCharCode(c.charCodeAt(0) + 128))
    .replace(/\\\\/g, "\\");
}

/** Lê os argumentos de uma entidade: "('a',$,#3,(1.,2.),.ENUM.,IFCLABEL('x'))". */
function lerArgs(texto: string): Valor[] {
  let i = 0;
  const pular = () => {
    while (i < texto.length && /\s/.test(texto[i])) i++;
  };
  function valor(): Valor {
    pular();
    const c = texto[i];
    if (c === "'") {
      let s = "";
      i++;
      while (i < texto.length) {
        if (texto[i] === "'") {
          if (texto[i + 1] === "'") {
            s += "'";
            i += 2;
            continue;
          }
          i++;
          break;
        }
        s += texto[i++];
      }
      return decodificarStep(s);
    }
    if (c === "(") return lista();
    if (c === "$" || c === "*") {
      i++;
      return null;
    }
    if (c === "#") {
      const m = /^#(\d+)/.exec(texto.slice(i));
      i += m ? m[0].length : 1;
      return { ref: m ? Number(m[1]) : -1 };
    }
    if (c === ".") {
      const fim = texto.indexOf(".", i + 1);
      if (fim < 0) {
        i = texto.length; // enum sem ponto final (arquivo corrompido): sem isto o laço nunca avançava
        return null;
      }
      const e = texto.slice(i + 1, fim);
      i = fim + 1;
      return { enum: e };
    }
    if (c === '"') {
      const fim = texto.indexOf('"', i + 1);
      i = fim < 0 ? texto.length : fim + 1;
      return null; // binário: não usado
    }
    const m = /^[A-Z_][A-Z0-9_]*/i.exec(texto.slice(i));
    if (m) {
      i += m[0].length;
      pular();
      const args = lista();
      return { tipo: m[0].toUpperCase(), valor: args.length === 1 ? args[0] : args };
    }
    const n = /^[-+]?(\d+\.?\d*|\.\d+)(E[-+]?\d+)?/i.exec(texto.slice(i));
    if (n) {
      i += n[0].length;
      return Number(n[0]);
    }
    i++;
    return null;
  }
  function lista(): Valor[] {
    const out: Valor[] = [];
    pular();
    if (texto[i] !== "(") return out;
    i++;
    pular();
    if (texto[i] === ")") {
      i++;
      return out;
    }
    while (i < texto.length) {
      out.push(valor());
      pular();
      if (texto[i] === ",") {
        i++;
        continue;
      }
      if (texto[i] === ")") {
        i++;
        break;
      }
      i++;
    }
    return out;
  }
  return lista();
}

/** Separa as instruções da seção DATA respeitando ';' dentro de textos entre aspas. */
function instrucoes(data: string): string[] {
  const out: string[] = [];
  let ini = 0;
  let aspas = false;
  for (let i = 0; i < data.length; i++) {
    const c = data[i];
    if (c === "'") aspas = !aspas; // '' (aspas escapadas) inverte duas vezes: continua dentro
    else if (c === ";" && !aspas) {
      out.push(data.slice(ini, i).trim());
      ini = i + 1;
    }
  }
  return out;
}

export function lerEntidades(texto: string): Map<number, Entidade> {
  const ini = texto.search(/\bDATA\s*;/i);
  const fim = texto.search(/\bENDSEC\s*;\s*END-ISO-10303-21/i);
  const mapa = new Map<number, Entidade>();
  if (ini < 0) return mapa;
  const data = texto.slice(texto.indexOf(";", ini) + 1, fim > ini ? fim : undefined);
  for (const inst of instrucoes(data)) {
    const m = /^#(\d+)\s*=\s*([A-Z0-9_]+)\s*(\(.*)$/is.exec(inst);
    if (!m) continue;
    mapa.set(Number(m[1]), { id: Number(m[1]), tipo: m[2].toUpperCase(), args: lerArgs(m[3]) });
  }
  return mapa;
}

// ---------- o que vira item ----------

type Regra = { categoria: string; medida: "area" | "contagem" | "comprimento"; quantidades?: string[]; prefixo?: string };

const AREA_PAREDE = ["NetSideArea", "GrossSideArea", "NetArea", "GrossArea"];
const AREA_PISO = ["NetFloorArea", "GrossFloorArea", "NetArea", "GrossArea"];
const AREA = ["NetArea", "GrossArea", "NetSideArea", "GrossSideArea"];

/** Classe IFC -> como medir. Classes fora daqui são ignoradas (estrutura espacial, eixos, anotações...). */
const REGRAS: Record<string, Regra> = {
  IFCSPACE: { categoria: "Revestimentos", medida: "area", quantidades: AREA_PISO, prefixo: "Piso " },
  IFCWALL: { categoria: "Alvenaria", medida: "area", quantidades: AREA_PAREDE },
  IFCWALLSTANDARDCASE: { categoria: "Alvenaria", medida: "area", quantidades: AREA_PAREDE },
  IFCSLAB: { categoria: "Estrutura", medida: "area", quantidades: AREA },
  IFCCOVERING: { categoria: "Revestimentos", medida: "area", quantidades: AREA },
  IFCROOF: { categoria: "Cobertura", medida: "area", quantidades: AREA },
  IFCCURTAINWALL: { categoria: "Esquadrias", medida: "area", quantidades: AREA },
  IFCRAILING: { categoria: "Serralheria", medida: "comprimento", quantidades: ["Length"] },
  IFCDOOR: { categoria: "Esquadrias", medida: "contagem" },
  IFCWINDOW: { categoria: "Esquadrias", medida: "contagem" },
  IFCSANITARYTERMINAL: { categoria: "Louças e metais", medida: "contagem" },
  IFCLIGHTFIXTURE: { categoria: "Elétrica", medida: "contagem" },
  IFCOUTLET: { categoria: "Elétrica", medida: "contagem" },
  IFCSWITCHINGDEVICE: { categoria: "Elétrica", medida: "contagem" },
  IFCFURNISHINGELEMENT: { categoria: "Mobiliário", medida: "contagem" },
  IFCFURNITURE: { categoria: "Mobiliário", medida: "contagem" },
  IFCFLOWTERMINAL: { categoria: "Instalações", medida: "contagem" },
  IFCVALVE: { categoria: "Hidráulica", medida: "contagem" },
};

const NOME_CLASSE: Record<string, string> = {
  IFCSPACE: "Ambiente", IFCWALL: "Parede", IFCWALLSTANDARDCASE: "Parede", IFCSLAB: "Laje", IFCCOVERING: "Revestimento",
  IFCROOF: "Cobertura", IFCCURTAINWALL: "Pele de vidro", IFCRAILING: "Guarda-corpo", IFCDOOR: "Porta", IFCWINDOW: "Janela",
  IFCSANITARYTERMINAL: "Louça sanitária", IFCLIGHTFIXTURE: "Luminária", IFCOUTLET: "Tomada", IFCSWITCHINGDEVICE: "Interruptor",
  IFCFURNISHINGELEMENT: "Mobiliário", IFCFURNITURE: "Mobiliário", IFCFLOWTERMINAL: "Terminal", IFCVALVE: "Registro",
};

const texto = (v: Valor | undefined): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);

/** Fator para metros (comprimento) e m² (área) a partir de IfcUnitAssignment. Padrão: metro e m². */
function fatores(ents: Map<number, Entidade>): { comprimento: number; area: number } {
  const PREFIXO: Record<string, number> = { MILLI: 1e-3, CENTI: 1e-2, DECI: 1e-1, KILO: 1e3 };
  const f = { comprimento: 1, area: 1 };
  for (const e of ents.values()) {
    if (e.tipo !== "IFCSIUNIT") continue;
    const tipo = ehEnum(e.args[1]) ? e.args[1].enum : "";
    const pre = ehEnum(e.args[2]) ? PREFIXO[e.args[2].enum] ?? 1 : 1;
    if (tipo === "LENGTHUNIT") f.comprimento = pre;
    if (tipo === "AREAUNIT") f.area = pre * pre;
  }
  return f;
}

export function importarIfc({ nome, bytes }: { nome: string; bytes: Uint8Array }): ResultadoImportacao {
  if (bytes.length === 0) return { erro: { codigo: "ARQUIVO_VAZIO", mensagem: "O arquivo está vazio." } };
  // .ifczip / .ifc compactado começa com "PK".
  if (bytes[0] === 0x50 && bytes[1] === 0x4b) {
    return { erro: { codigo: "FORMATO_NAO_SUPORTADO", mensagem: "Este IFC está compactado (IFCZIP). Descompacte ou exporte como .ifc comum." } };
  }
  let conteudo: string;
  try {
    conteudo = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    conteudo = new TextDecoder("windows-1252").decode(bytes);
  }
  if (!/^\s*ISO-10303-21\s*;/i.test(conteudo)) {
    return { erro: { codigo: "FORMATO_INVALIDO", mensagem: "Este arquivo não é um IFC em texto (não começa com ISO-10303-21). Exporte o modelo como IFC no Revit ou ArchiCAD." } };
  }
  if (!/END-ISO-10303-21\s*;\s*$/i.test(conteudo) || !/\bDATA\s*;/i.test(conteudo)) {
    return { erro: { codigo: "ARQUIVO_CORROMPIDO", mensagem: "O IFC está incompleto (o arquivo termina antes do fim). Exporte de novo." } };
  }
  const esquema = /FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'/i.exec(conteudo)?.[1] ?? null;
  const ents = lerEntidades(conteudo);
  const unid = fatores(ents);

  // Relações: elemento -> quantidades, material e pavimento.
  const quantidadesDe = new Map<number, Map<string, number>>();
  const materialDe = new Map<number, string>();
  const pavimentoDe = new Map<number, string>();
  const nomeDe = (id: number | undefined) => (id != null ? texto(ents.get(id)?.args[2]) : null);

  const lerQuantidades = (pset: Entidade): Map<string, number> => {
    const m = new Map<string, number>();
    const lista = pset.args[5];
    if (!Array.isArray(lista)) return m;
    for (const r of lista) {
      if (!ehRef(r)) continue;
      const q = ents.get(r.ref);
      if (!q || !q.tipo.startsWith("IFCQUANTITY")) continue;
      const n = texto(q.args[0]);
      const v = q.args[3];
      if (!n || typeof v !== "number") continue;
      const fator = q.tipo === "IFCQUANTITYAREA" ? unid.area : q.tipo === "IFCQUANTITYLENGTH" ? unid.comprimento : 1;
      m.set(n, v * fator);
    }
    return m;
  };

  // Reserva: muitos exportadores (ArchiCAD, Revit sem "quantidades base") põem a área só numa PROPRIEDADE
  // ("Area", "Área", "NetArea", "120_Pindala"...), às vezes como texto com vírgula: IFCLABEL('63,8').
  const areaPorPropriedade = new Map<number, { valor: number; nome: string; prioridade: number }>();
  const lerAreaDaPropriedade = (prop: Entidade): { valor: number; nome: string; prioridade: number } | null => {
    if (prop.tipo !== "IFCPROPERTYSINGLEVALUE") return null;
    const nome = texto(prop.args[0]);
    if (!nome) return null;
    const n = nome.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    if (!/(area|pindala|flache|superficie|surface)/.test(n) || /(volume|perimet|cross|section|projected|altura|height)/.test(n)) return null;
    const v = prop.args[2];
    let valor: number | null = null;
    if (v && typeof v === "object" && "tipo" in v) {
      if (typeof v.valor === "number") valor = v.tipo === "IFCAREAMEASURE" ? v.valor * unid.area : v.valor;
      else if (typeof v.valor === "string") {
        const s = v.valor.replace(/\s|m²|m2/gi, "");
        const num = /^\d+(\.\d{3})*(,\d+)?$/.test(s) ? Number(s.replace(/\./g, "").replace(",", ".")) : Number(s);
        valor = Number.isFinite(num) ? num : null;
      }
    }
    if (valor == null || valor <= 0) return null;
    // "Net/Neto/Liquida" vale mais que a área bruta; o resto empata e vence o primeiro.
    const prioridade = /(net|neto|liquid|netto)/.test(n) ? 2 : /(gross|bruta|brutto|ehitatav|hoonealune)/.test(n) ? 0 : 1;
    return { valor, nome, prioridade };
  };

  const nomeMaterial = (id: number, prof = 0): string | null => {
    const e = ents.get(id);
    if (!e || prof > 4) return null;
    if (e.tipo === "IFCMATERIAL") return texto(e.args[0]);
    if (e.tipo === "IFCMATERIALLAYERSETUSAGE" && ehRef(e.args[0])) return nomeMaterial(e.args[0].ref, prof + 1);
    if (e.tipo === "IFCMATERIALLAYERSET" && Array.isArray(e.args[0])) {
      const nomes = e.args[0].filter(ehRef).map((r) => nomeMaterial(r.ref, prof + 1)).filter(Boolean);
      return texto(e.args[1]) ?? (nomes.length ? nomes.join(" + ") : null);
    }
    if (e.tipo === "IFCMATERIALLAYER" && ehRef(e.args[0])) return nomeMaterial(e.args[0].ref, prof + 1);
    if (e.tipo === "IFCMATERIALLIST" && Array.isArray(e.args[0])) {
      const nomes = e.args[0].filter(ehRef).map((r) => nomeMaterial(r.ref, prof + 1)).filter(Boolean);
      return nomes.length ? nomes.join(" + ") : null;
    }
    return null;
  };

  for (const e of ents.values()) {
    const alvos = (e.args[4] && Array.isArray(e.args[4]) ? e.args[4] : []).filter(ehRef).map((r) => r.ref);
    const destino = e.args[5];
    if (e.tipo === "IFCRELDEFINESBYPROPERTIES" && ehRef(destino)) {
      const pset = ents.get(destino.ref);
      if (pset?.tipo === "IFCPROPERTYSET" && Array.isArray(pset.args[4])) {
        for (const r of pset.args[4].filter(ehRef)) {
          const prop = ents.get(r.ref);
          const a = prop ? lerAreaDaPropriedade(prop) : null;
          if (!a) continue;
          for (const alvo of alvos) {
            const atual = areaPorPropriedade.get(alvo);
            if (!atual || a.prioridade > atual.prioridade) areaPorPropriedade.set(alvo, a);
          }
        }
        continue;
      }
      if (pset?.tipo !== "IFCELEMENTQUANTITY") continue;
      const q = lerQuantidades(pset);
      for (const a of alvos) quantidadesDe.set(a, new Map([...(quantidadesDe.get(a) ?? []), ...q]));
    } else if (e.tipo === "IFCRELASSOCIATESMATERIAL" && ehRef(destino)) {
      const m = nomeMaterial(destino.ref);
      if (m) for (const a of alvos) materialDe.set(a, m);
    } else if (e.tipo === "IFCRELCONTAINEDINSPATIALSTRUCTURE" && ehRef(destino)) {
      const est = ents.get(destino.ref);
      const nomeEst = est ? texto(est.args[2]) : null;
      if (est?.tipo === "IFCBUILDINGSTOREY" && nomeEst) for (const a of alvos) pavimentoDe.set(a, nomeEst);
    } else if (e.tipo === "IFCRELAGGREGATES" && ehRef(e.args[4]) && Array.isArray(e.args[5])) {
      // Ambientes costumam pendurar no pavimento por agregação (aqui o "pai" vem ANTES dos filhos).
      const pai = ents.get(e.args[4].ref);
      const nomePai = pai ? texto(pai.args[2]) : null;
      if (pai?.tipo === "IFCBUILDINGSTOREY" && nomePai) {
        for (const r of e.args[5].filter(ehRef)) if (!pavimentoDe.has(r.ref)) pavimentoDe.set(r.ref, nomePai);
      }
    }
  }

  // Agrupa por classe + nome + material + pavimento, na ordem em que aparecem no arquivo.
  type Grupo = { regra: Regra; classe: string; nome: string; material: string | null; nivel: string | null; n: number; soma: number; semQtd: number; guids: string[]; daPropriedade?: string };
  const grupos = new Map<string, Grupo>();
  for (const e of [...ents.values()].sort((a, b) => a.id - b.id)) {
    const regra = REGRAS[e.tipo];
    if (!regra) continue;
    const nomeEl = texto(e.args[2]) ?? (e.tipo === "IFCSPACE" ? texto(e.args[7]) : null) ?? NOME_CLASSE[e.tipo];
    const material = materialDe.get(e.id) ?? null;
    const nivel = pavimentoDe.get(e.id) ?? null;
    const chave = [e.tipo === "IFCWALLSTANDARDCASE" ? "IFCWALL" : e.tipo, nomeEl, material, nivel].join("|");
    const g = grupos.get(chave) ?? { regra, classe: e.tipo, nome: nomeEl, material, nivel, n: 0, soma: 0, semQtd: 0, guids: [] };
    g.n++;
    if (g.guids.length < 50 && texto(e.args[0])) g.guids.push(texto(e.args[0])!);
    if (regra.medida !== "contagem") {
      const qs = quantidadesDe.get(e.id);
      let v = regra.quantidades?.map((k) => qs?.get(k)).find((x) => typeof x === "number");
      if (v == null && regra.medida === "area") {
        const p = areaPorPropriedade.get(e.id);
        if (p) {
          v = p.valor;
          g.daPropriedade = p.nome;
        }
      }
      if (v == null) g.semQtd++;
      else g.soma += v;
    }
    grupos.set(chave, g);
  }

  const itens: ItemImportado[] = [];
  const avisos: AvisoImportacao[] = [];
  let linha = 0;
  for (const g of grupos.values()) {
    linha++;
    let quantidade: number | null;
    let unidade: string;
    let descricao = g.regra.prefixo ? `${g.regra.prefixo}${g.nome}` : g.nome;
    if (g.regra.medida === "contagem") {
      quantidade = g.n;
      unidade = "un";
    } else {
      unidade = g.regra.medida === "area" ? "m2" : "m";
      descricao += g.regra.medida === "area" ? " (área)" : " (comprimento)";
      if (g.semQtd === g.n) {
        quantidade = null;
        avisos.push({
          linha,
          codigo: "QUANTIDADE_AUSENTE",
          mensagem: `"${descricao}": o modelo não declara a ${g.regra.medida === "area" ? "área" : "medida"} (exporte o IFC com as quantidades base). Informe a medida.`,
        });
      } else {
        quantidade = Math.round(g.soma * 100) / 100;
        if (g.semQtd > 0) {
          avisos.push({ linha, codigo: "QUANTIDADE_AUSENTE", mensagem: `"${descricao}": ${g.semQtd} de ${g.n} elementos sem quantidade declarada; a soma pode estar baixa.` });
        }
      }
    }
    if (g.material) descricao += ` — ${g.material}`;
    itens.push({
      linha,
      categoria: g.regra.categoria,
      descricao,
      quantidade,
      unidade,
      nivel: g.nivel,
      extras: { origem_ifc: { classe: g.classe, elementos: g.n, global_ids: g.guids, esquema, ...(g.material ? { material: g.material } : {}), ...(g.daPropriedade ? { area_da_propriedade: g.daPropriedade } : {}) } },
    });
  }

  if (itens.length === 0) {
    avisos.push({ linha: null, codigo: "SEM_DADOS", mensagem: "O IFC não tem ambientes, paredes, portas, janelas, louças ou revestimentos para listar." });
  }
  return {
    origem: { arquivo: nome, formato: "ifc", software: "desconhecido", aba: null, delimitador: null, codificacao: null, linhas_lidas: ents.size, linhas_descartadas: 0 },
    itens,
    avisos,
  };
}
