// Formatação para a tela: moeda, unidades e a frase de compra ("180 m² → 2 latas 18 L").

import type { Objetivo } from "./tipos";

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const numero = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

export const reais = (v: number) => moeda.format(v);

/** Valor curto para as pontas da cota: R$ 659 (sem centavos quando passa de R$ 100). */
export const reaisCurto = (v: number) =>
  v >= 100 ? `R$ ${Math.round(v).toLocaleString("pt-BR")}` : moeda.format(v);

const UNIDADES: Record<string, string> = { m2: "m²", m3: "m³", m: "m", l: "L", kg: "kg", un: "un" };

export const unidade = (u?: string | null) => (u ? UNIDADES[u.toLowerCase()] ?? u : "");

export const quantidade = (q?: number | null, u?: string | null) =>
  q == null ? "" : `${numero.format(q)} ${unidade(u)}`.trim();

const PLURAIS: Record<string, string> = {
  lata: "latas", latão: "latões", galão: "galões", caixa: "caixas", saco: "sacos", balde: "baldes",
  rolo: "rolos", barra: "barras", pacote: "pacotes", unidade: "unidades", peça: "peças", kit: "kits",
};

/** "lata 18 L" + 2 → "2 latas 18 L" · "caixa 1,8m²" + 30 → "30 caixas 1,8 m²" · "6 L" + 2 → "2 × 6 L". */
export function embalagens(n: number, emb: string): string {
  const limpa = emb.replace(/(\d)\s*m²/g, "$1 m²").trim();
  const [primeira, ...resto] = limpa.split(/\s+/);
  const chave = primeira.toLowerCase();
  if (chave in PLURAIS) {
    const nome = n === 1 ? primeira : PLURAIS[chave];
    return [String(n), nome, ...resto].join(" ");
  }
  return `${n} × ${limpa}`;
}


/** Opções de alternativa do "Pesquisar de novo", na ordem em que aparecem. */
export const OBJETIVOS: { objetivo: Objetivo; rotulo: string; dica: string }[] = [
  { objetivo: "qualidade", rotulo: "Maior qualidade", dica: "Linha superior, mais durável ou com melhor acabamento" },
  { objetivo: "preco", rotulo: "Menor preço", dica: "Opção mais econômica para a mesma aplicação" },
  { objetivo: "semelhante", rotulo: "Semelhante de outra marca", dica: "Produto equivalente de outra marca" },
];

/** Texto curto da loja da região para a linha do item: "a 4,2 km de carro (aprox.)" ou null sem distância. */
export function distanciaDaLoja(km: number | null | undefined): string | null {
  if (km == null || !Number.isFinite(km) || km <= 0) return null;
  return `a ${km.toFixed(1).replace(".", ",")} km de carro (aprox.)`;
}
