// Regras puras do resultado da Fatia C (sem React: é o que resultado.test.ts exercita).
// Entrada: as linhas de `orcamento_itens` e a linha de `orcamentos` (logistica, viabilidade, ganho) que o
// useOrcamento entrega. Referência visual: Figma, tela 08 · Documento de orçamento.

import { embalagens, reais } from "../orcamento/formato";
import type { ItemLinha, Viabilidade } from "@/lib/orcamento/tipos";

export interface LinhaDocumento {
  id: string;
  rotulo: string;
  /** "30 caixas 1,62 m²" */
  detalhe: string;
  total: number;
}

const centavos = (v: number) => Math.round(v * 100) / 100;

/** Complemento sugerido (E2) só conta depois que o arquiteto aceitou (a API também ignora os recusados). */
export const entraNaConta = (i: Pick<ItemLinha, "sugerido" | "aceito">) => !(i.sugerido && i.aceito !== true);

/** Itens que têm preço de verdade: status `definido`, com preço médio e número de embalagens. */
export function linhasDocumento(itens: ItemLinha[]): LinhaDocumento[] {
  return itens
    .filter(entraNaConta)
    .filter((i) => i.status === "definido" && (i.preco_emb_med ?? 0) > 0 && (i.qtd_embalagens ?? 0) > 0)
    .map((i) => ({
      id: i.id,
      rotulo: i.produto_normalizado || i.descricao,
      detalhe: i.embalagem ? embalagens(i.qtd_embalagens as number, i.embalagem) : `${i.qtd_embalagens} un`,
      total: centavos((i.preco_emb_med as number) * (i.qtd_embalagens as number)),
    }));
}

export const subtotal = (linhas: LinhaDocumento[]) => centavos(linhas.reduce((s, l) => s + l.total, 0));

export interface ForaDoSubtotal {
  pendentes: number;
  /** não encontrados, com erro, ainda buscando ou definidos sem quantidade de embalagens */
  semPreco: number;
  total: number;
}

/** Itens que existem na lista mas não entram no subtotal (a nota do documento precisa dizer quantos). */
export function foraDoSubtotal(itens: ItemLinha[]): ForaDoSubtotal {
  const validos = itens.filter(entraNaConta);
  const dentro = new Set(linhasDocumento(itens).map((l) => l.id));
  const fora = validos.filter((i) => !dentro.has(i.id));
  const pendentes = fora.filter((i) => i.status === "pendente_especificacao").length;
  return { pendentes, semPreco: fora.length - pendentes, total: fora.length };
}

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

/** Nota do rodapé do documento. Frete está em pausa: o texto diz que ele não está incluído. */
export function notaDocumento(fora: ForaDoSubtotal): string {
  const partes = ["Frete"];
  if (fora.pendentes) partes.push(plural(fora.pendentes, "item pendente", "itens pendentes"));
  if (fora.semPreco) partes.push(plural(fora.semPreco, "item sem preço", "itens sem preço"));
  const quais = partes.length > 1 ? `${partes.slice(0, -1).join(", ")} e ${partes[partes.length - 1]}` : partes[0];
  const verbo = partes.length > 1 || fora.total ? "não incluídos" : "não incluído";
  return (
    `${quais} ${verbo}. Estimativa sujeita à confirmação de preços e disponibilidade. ` +
    "Os preços vêm de uma pesquisa automática em lojas on-line, com a fonte em cada item: confirme com o fornecedor antes de comprar."
  );
}

export type Tom = "sim" | "talvez" | "nao";
export interface Veredito {
  tom: Tom;
  icone: string;
  titulo: string;
}

/** Nunca afirma "cabe" sem avisar quando há itens sem preço (`completo === false`). */
export function veredito(v: Viabilidade): Veredito {
  if (v.completo === false) return { tom: "talvez", icone: "⚠", titulo: "Ainda não dá para afirmar" };
  if (v.cabe) return { tom: "sim", icone: "✓", titulo: "Cabe no orçamento" };
  if (v.cabe_no_minimo) return { tom: "talvez", icone: "⚠", titulo: "Cabe só no menor preço" };
  return { tom: "nao", icone: "✕", titulo: "Não cabe no orçamento" };
}

/** O título do veredito já diz "Ainda não dá para afirmar": tira essa frase do início do resumo para não repetir. */
export function resumoParaTela(v: Viabilidade): string {
  const r = v.resumo ?? "";
  const prefixo = "Ainda não dá para afirmar: ";
  if (v.completo === false && r.startsWith(prefixo)) {
    const resto = r.slice(prefixo.length);
    return resto.charAt(0).toUpperCase() + resto.slice(1);
  }
  return r;
}

/** Link do Excel (E11). `base` vem de NEXT_PUBLIC_API_URL; sem ele não há como baixar (botão desativado). */
export function urlExportar(id: string, base: string | undefined = process.env.NEXT_PUBLIC_API_URL): string | null {
  const b = (base ?? "").trim().replace(/\/+$/, "");
  return b ? `${b}/orcamentos/${encodeURIComponent(id)}/exportar.xlsx` : null;
}

export const faixa = (v: Viabilidade) =>
  v.total_min != null && v.total_max != null ? `${reais(v.total_min)} a ${reais(v.total_max)}` : null;

export function dataCurta(iso: string | Date = new Date()): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}
