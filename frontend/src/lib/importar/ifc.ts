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

type Medida = "area" | "volume" | "comprimento";
/** Medidas tentadas em ordem; a primeira que o elemento declara vale. `contar` = item discreto (conta em un). */
type Regra = { categoria: string; contar?: boolean; medidas?: { medida: Medida; nomes: string[] }[]; prefixo?: string; areaPorComprimentoAltura?: boolean };

// Nomes de quantidade aceitos (sem diferenciar maiúsculas). "Projected Component/Skin Area" e "Skin/Component Volume" são do
// ArchiCAD: ele guarda as medidas por camada (IfcPhysicalComplexQuantity "Component 1…"), não as Qto_* padrão.
const SKIN_AREA = "Projected Component/Skin Area";
const AREA_PAREDE = ["NetSideArea", "GrossSideArea", "NetArea", "GrossArea", SKIN_AREA];
const AREA_PISO = ["NetFloorArea", "GrossFloorArea", "NetArea", "GrossArea"];
const AREA = ["NetArea", "GrossArea", "NetSideArea", "GrossSideArea", SKIN_AREA];
const VOLUME = ["NetVolume", "GrossVolume", "Volume", "Skin/Component Volume"];
const area = (nomes: string[]) => ({ medida: "area" as const, nomes });
const volume = { medida: "volume" as const, nomes: VOLUME };

/** Classe IFC -> como medir. Classes fora daqui são ignoradas (estrutura espacial, eixos, anotações...). */
const REGRAS: Record<string, Regra> = {
  IFCSPACE: { categoria: "Revestimentos", medidas: [area(AREA_PISO)], prefixo: "Piso " },
  IFCWALL: { categoria: "Alvenaria", medidas: [area(AREA_PAREDE)], areaPorComprimentoAltura: true },
  IFCWALLSTANDARDCASE: { categoria: "Alvenaria", medidas: [area(AREA_PAREDE)], areaPorComprimentoAltura: true },
  IFCSLAB: { categoria: "Estrutura", medidas: [area(AREA)] },
  IFCCOVERING: { categoria: "Revestimentos", medidas: [area(AREA)] },
  IFCROOF: { categoria: "Cobertura", medidas: [area(AREA)] },
  IFCCURTAINWALL: { categoria: "Esquadrias", medidas: [area(AREA)] },
  IFCRAILING: { categoria: "Serralheria", medidas: [{ medida: "comprimento", nomes: ["Length"] }] },
  IFCBEAM: { categoria: "Estrutura", medidas: [volume] },
  IFCCOLUMN: { categoria: "Estrutura", medidas: [volume] },
  IFCFOOTING: { categoria: "Estrutura", medidas: [volume] },
  IFCSTAIRFLIGHT: { categoria: "Escadas e rampas", medidas: [area(AREA), volume] },
  IFCRAMP: { categoria: "Escadas e rampas", medidas: [area(AREA), volume] },
  IFCRAMPFLIGHT: { categoria: "Escadas e rampas", medidas: [area(AREA), volume] },
  IFCDOOR: { categoria: "Esquadrias", contar: true },
  IFCWINDOW: { categoria: "Esquadrias", contar: true },
  IFCSANITARYTERMINAL: { categoria: "Louças e metais", contar: true },
  IFCLIGHTFIXTURE: { categoria: "Elétrica", contar: true },
  IFCOUTLET: { categoria: "Elétrica", contar: true },
  IFCSWITCHINGDEVICE: { categoria: "Elétrica", contar: true },
  IFCFURNISHINGELEMENT: { categoria: "Mobiliário", contar: true },
  IFCFURNITURE: { categoria: "Mobiliário", contar: true },
  IFCFLOWTERMINAL: { categoria: "Instalações", contar: true },
  IFCVALVE: { categoria: "Hidráulica", contar: true },
  IFCTRANSPORTELEMENT: { categoria: "Elevadores e transporte", contar: true },
  IFCBUILDINGELEMENTPROXY: { categoria: "Elementos genéricos", contar: true },
};

const NOME_CLASSE: Record<string, string> = {
  IFCSPACE: "Ambiente", IFCWALL: "Parede", IFCWALLSTANDARDCASE: "Parede", IFCSLAB: "Laje", IFCCOVERING: "Revestimento",
  IFCROOF: "Cobertura", IFCCURTAINWALL: "Pele de vidro", IFCRAILING: "Guarda-corpo", IFCDOOR: "Porta", IFCWINDOW: "Janela",
  IFCSANITARYTERMINAL: "Louça sanitária", IFCLIGHTFIXTURE: "Luminária", IFCOUTLET: "Tomada", IFCSWITCHINGDEVICE: "Interruptor",
  IFCFURNISHINGELEMENT: "Mobiliário", IFCFURNITURE: "Mobiliário", IFCFLOWTERMINAL: "Terminal", IFCVALVE: "Registro",
  IFCBEAM: "Viga", IFCCOLUMN: "Pilar", IFCFOOTING: "Fundação", IFCSTAIRFLIGHT: "Lance de escada", IFCRAMP: "Rampa",
  IFCRAMPFLIGHT: "Lance de rampa", IFCTRANSPORTELEMENT: "Elevador", IFCBUILDINGELEMENTPROXY: "Elemento genérico",
};

const texto = (v: Valor | undefined): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);

type Fatores = { comprimento: number; area: number; volume: number };
const PREFIXO: Record<string, number> = { MICRO: 1e-6, MILLI: 1e-3, CENTI: 1e-2, DECI: 1e-1, HECTO: 1e2, KILO: 1e3, MEGA: 1e6 };

/** A unidade da quantidade/propriedade prevalece sobre UnitsInContext. Referência inválida não vira metro. */
function fatorUnidade(ents: Map<number, Entidade>, id: number, medida: Medida, caminho = new Set<number>()): number | null {
  if (caminho.has(id) || caminho.size >= 16) return null;
  caminho.add(id);
  const u = ents.get(id);
  const tipos = { comprimento: "LENGTHUNIT", area: "AREAUNIT", volume: "VOLUMEUNIT" };
  const nomes = { comprimento: "METRE", area: "SQUARE_METRE", volume: "CUBIC_METRE" };
  if (!u || !ehEnum(u.args[1]) || u.args[1].enum !== tipos[medida]) return null;
  if (u.tipo === "IFCSIUNIT") {
    if (!ehEnum(u.args[3]) || u.args[3].enum !== nomes[medida]) return null;
    const pre = ehEnum(u.args[2]) ? PREFIXO[u.args[2].enum] : 1;
    return pre === undefined ? null : pre ** ({ comprimento: 1, area: 2, volume: 3 }[medida]);
  }
  if (u.tipo !== "IFCCONVERSIONBASEDUNIT" || !ehRef(u.args[3])) return null;
  const conv = ents.get(u.args[3].ref);
  const base = conv?.args[0];
  const valor = typeof base === "number" ? base : base && typeof base === "object" && "valor" in base ? base.valor : null;
  if (typeof valor !== "number" || !Number.isFinite(valor) || valor <= 0 || !ehRef(conv?.args[1] as Valor)) return null;
  const fator = fatorUnidade(ents, (conv!.args[1] as Ref).ref, medida, caminho);
  return fator === null ? null : valor * fator;
}

/**
 * Fator para metros, m² e m³ a partir de IfcUnitAssignment (ou, sem ele, das unidades soltas no arquivo).
 * Aceita unidade SI com prefixo (milímetro) e unidade convertida (IfcConversionBasedUnit: pé, polegada).
 */
function fatores(ents: Map<number, Entidade>): Fatores {
  const f: Fatores = { comprimento: 1, area: 1, volume: 1 };
  const CAMPOS: Record<string, Medida> = { LENGTHUNIT: "comprimento", AREAUNIT: "area", VOLUMEUNIT: "volume" };
  const aplicar = (u: Entidade) => {
    const tipo = ehEnum(u.args[1]) ? u.args[1].enum : "";
    const campo = CAMPOS[tipo];
    if (!campo) return;
    f[campo] = fatorUnidade(ents, u.id, campo) ?? NaN;
  };
  const atribuicao = [...ents.values()].find((e) => e.tipo === "IFCUNITASSIGNMENT");
  const lista = atribuicao && Array.isArray(atribuicao.args[0]) ? atribuicao.args[0].filter(ehRef).map((r) => ents.get(r.ref)).filter((x): x is Entidade => !!x) : null;
  if (lista && lista.length) {
    for (const u of lista) aplicar(u);
  } else {
    const todas = [...ents.values()];
    for (const u of todas) if (u.tipo === "IFCSIUNIT") aplicar(u);
    for (const u of todas) if (u.tipo === "IFCCONVERSIONBASEDUNIT") aplicar(u); // a unidade convertida vence a SI solta
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
  const camadasDe = new Set<number>(); // elementos cuja área vem de várias camadas (ArchiCAD)
  const materialDe = new Map<number, string>();
  const pavimentoDe = new Map<number, string>();
  const nomeDe = (id: number | undefined) => (id != null ? texto(ents.get(id)?.args[2]) : null);

  /**
   * Lê um IfcElementQuantity. Além das quantidades simples, entra nas IfcPhysicalComplexQuantity (o ArchiCAD guarda as
   * medidas por camada: "Component 1", "Component 2"…). Nomes repetidos: volume soma as camadas; as demais medidas valem
   * pelo maior valor (a área da pele de cada camada é a face da parede; somar contaria a parede várias vezes).
   */
  const lerQuantidades = (pset: Entidade): { valores: Map<string, number>; porCamadas: boolean } => {
    const acum = new Map<string, number[]>();
    const coletar = (id: number, prof: number) => {
      const q = ents.get(id);
      if (!q || prof > 4) return;
      if (q.tipo === "IFCPHYSICALCOMPLEXQUANTITY") {
        if (Array.isArray(q.args[2])) for (const r of q.args[2]) if (ehRef(r)) coletar(r.ref, prof + 1);
        return;
      }
      if (!q.tipo.startsWith("IFCQUANTITY")) return;
      const n = texto(q.args[0]);
      const v = q.args[3];
      if (!n || typeof v !== "number" || !Number.isFinite(v) || v <= 0) return;
      const medidas: Record<string, Medida> = { IFCQUANTITYAREA: "area", IFCQUANTITYLENGTH: "comprimento", IFCQUANTITYVOLUME: "volume" };
      const medida = medidas[q.tipo];
      const fator = medida ? (ehRef(q.args[2]) ? fatorUnidade(ents, q.args[2].ref, medida) : unid[medida]) : 1;
      if (fator === null || !Number.isFinite(v * fator) || fator <= 0) return;
      const k = n.toLowerCase();
      const lista = acum.get(k) ?? [];
      lista.push(v * fator);
      acum.set(k, lista);
    };
    if (Array.isArray(pset.args[5])) for (const r of pset.args[5]) if (ehRef(r)) coletar(r.ref, 0);
    const valores = new Map<string, number>();
    let porCamadas = false;
    for (const [k, vs] of acum) {
      valores.set(k, k.includes("volume") ? vs.reduce((x, y) => x + y, 0) : Math.max(...vs));
      if (vs.length > 1 && k === SKIN_AREA.toLowerCase()) porCamadas = true;
    }
    return { valores, porCamadas };
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
      if (typeof v.valor === "number") {
        const fator = ehRef(prop.args[3]) ? fatorUnidade(ents, prop.args[3].ref, "area") : v.tipo === "IFCAREAMEASURE" ? unid.area : 1;
        valor = fator === null ? null : v.valor * fator;
      }
      else if (typeof v.valor === "string") {
        const s = v.valor.replace(/\s|m²|m2/gi, "");
        const num = /^\d+(\.\d{3})*(,\d+)?$/.test(s) ? Number(s.replace(/\./g, "").replace(",", ".")) : Number(s);
        valor = Number.isFinite(num) ? num : null;
      }
    }
    if (valor == null || !Number.isFinite(valor) || valor <= 0) return null;
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
      for (const a of alvos) {
        quantidadesDe.set(a, new Map([...(quantidadesDe.get(a) ?? []), ...q.valores]));
        if (q.porCamadas) camadasDe.add(a);
      }
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

  // Agrupa por classe + nome + material + pavimento (+ a medida usada), na ordem em que aparecem no arquivo.
  type Grupo = {
    regra: Regra; classe: string; nome: string; material: string | null; nivel: string | null; medida: Medida | "contagem";
    n: number; soma: number; semQtd: number; guids: string[]; daPropriedade?: string; calculadas: number; porCamadas: number;
  };
  const grupos = new Map<string, Grupo>();
  for (const e of [...ents.values()].sort((a, b) => a.id - b.id)) {
    const regra = REGRAS[e.tipo];
    if (!regra) continue;
    const nomeEl = texto(e.args[2]) ?? (e.tipo === "IFCSPACE" ? texto(e.args[7]) : null) ?? NOME_CLASSE[e.tipo];
    const material = materialDe.get(e.id) ?? null;
    const nivel = pavimentoDe.get(e.id) ?? null;

    // Qual medida este elemento declara? A primeira da lista da classe que existir; senão, as reservas.
    let medida: Medida | null = null;
    let v: number | undefined;
    let daPropriedade: string | undefined;
    let calculada = false;
    let nomeUsado: string | undefined;
    if (!regra.contar) {
      const qs = quantidadesDe.get(e.id);
      for (const m of regra.medidas ?? []) {
        const nome = m.nomes.find((k) => typeof qs?.get(k.toLowerCase()) === "number");
        if (nome) {
          medida = m.medida;
          v = qs!.get(nome.toLowerCase());
          nomeUsado = nome;
          break;
        }
      }
      if (v == null && regra.areaPorComprimentoAltura) {
        const comp = qs?.get("length");
        const alt = qs?.get("height") ?? qs?.get("nominalheight");
        if (comp != null && alt != null && comp > 0 && alt > 0) {
          medida = "area";
          v = comp * alt;
          calculada = true;
        }
      }
      if (v == null && regra.medidas?.[0]?.medida === "area") {
        const p = areaPorPropriedade.get(e.id);
        if (p) {
          medida = "area";
          v = p.valor;
          daPropriedade = p.nome;
        }
      }
    }
    const medidaGrupo: Medida | "contagem" = regra.contar ? "contagem" : medida ?? regra.medidas?.[0]?.medida ?? "area";
    const chave = [e.tipo === "IFCWALLSTANDARDCASE" ? "IFCWALL" : e.tipo, nomeEl, material, nivel, medidaGrupo].join("|");
    const g = grupos.get(chave) ?? { regra, classe: e.tipo, nome: nomeEl, material, nivel, medida: medidaGrupo, n: 0, soma: 0, semQtd: 0, guids: [], calculadas: 0, porCamadas: 0 };
    g.n++;
    if (g.guids.length < 50 && texto(e.args[0])) g.guids.push(texto(e.args[0])!);
    if (!regra.contar) {
      if (v == null) g.semQtd++;
      else {
        g.soma += v;
        if (daPropriedade) g.daPropriedade = daPropriedade;
        if (calculada) g.calculadas++;
        if (nomeUsado?.toLowerCase() === SKIN_AREA.toLowerCase() && camadasDe.has(e.id)) g.porCamadas++;
      }
    }
    grupos.set(chave, g);
  }

  const itens: ItemImportado[] = [];
  const avisos: AvisoImportacao[] = [];
  let linha = 0;
  let elementosPorCamadas = 0;
  const ROTULO: Record<Medida, { unidade: string; sufixo: string; falta: string }> = {
    area: { unidade: "m2", sufixo: " (área)", falta: "a área" },
    volume: { unidade: "m3", sufixo: " (volume)", falta: "o volume" },
    comprimento: { unidade: "m", sufixo: " (comprimento)", falta: "a medida" },
  };
  for (const g of grupos.values()) {
    linha++;
    let quantidade: number | null;
    let unidade: string;
    let descricao = g.regra.prefixo ? `${g.regra.prefixo}${g.nome}` : g.nome;
    if (g.medida === "contagem") {
      quantidade = g.n;
      unidade = "un";
    } else {
      const rot = ROTULO[g.medida];
      unidade = rot.unidade;
      descricao += rot.sufixo;
      if (g.semQtd === g.n) {
        quantidade = null;
        avisos.push({
          linha,
          codigo: "QUANTIDADE_AUSENTE",
          mensagem: `"${descricao}": o modelo não declara ${rot.falta} (exporte o IFC com as quantidades base). Informe a medida.`,
        });
      } else {
        quantidade = Math.round(g.soma * 100) / 100;
        if (g.semQtd > 0) {
          avisos.push({ linha, codigo: "QUANTIDADE_AUSENTE", mensagem: `"${descricao}": ${g.semQtd} de ${g.n} elementos sem quantidade declarada; a soma pode estar baixa.` });
        }
        if (g.calculadas > 0) {
          avisos.push({ linha, codigo: "EXTRACAO_AMBIGUA", mensagem: `"${descricao}": a área de ${g.calculadas} elemento(s) foi calculada por comprimento × altura (o modelo não declara a área). Confira.` });
        }
      }
    }
    elementosPorCamadas += g.porCamadas;
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
  if (elementosPorCamadas > 0) {
    avisos.push({
      linha: null,
      codigo: "EXTRACAO_AMBIGUA",
      mensagem: `${elementosPorCamadas} elemento(s) trazem a área por camada (ArchiCAD). Usei a maior camada de cada elemento para não contar a mesma parede mais de uma vez. Confira.`,
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
