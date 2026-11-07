// Regras puras do resultado da Fatia C (sem React: é o que resultado.test.ts exercita).
// Entrada: as linhas de `orcamento_itens` e a linha de `orcamentos` (logistica, viabilidade, ganho) que o
// useOrcamento entrega. Referência visual: Figma, tela 08 · Documento de orçamento.

import { embalagens, quantidade as formatarQtd, reais, unidade as formatarUnidade } from "../orcamento/formato";
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

// ---------------------------------------------------------------------------------------------------------------
// Lista "Materiais" / "Fontes" / "Referência selecionada" (Figma, telas 05 e 06) a partir das linhas reais.

const hmm = (url?: string | null) => (typeof url === "string" && /^https?:\/\//i.test(url) ? url : null);

export interface FonteTela {
  loja: string;
  dominio: string;
  url: string | null;
  /** "R$ 489,90 / lata 18 L" */
  preco: string;
  data: string | null;
}

export type SituacaoItem = "precificado" | "pendente" | "sem-preco" | "buscando";

export interface ItemTela {
  id: string;
  nome: string;
  /** especificação: "Acetinado, 60 × 60 cm" ou a embalagem */
  detalhe: string;
  /** "Casa Forma · Revestimentos" (loja de menor preço + categoria) */
  loja: string;
  /** o que a obra precisa: "60 m²" */
  quantidade: string;
  /** "33 caixas 1,62 m²" */
  compra: string;
  total: number | null;
  /** "R$ 89,90 / m²" */
  unitario: string;
  situacao: SituacaoItem;
  /** texto quando não há preço: pergunta ao arquiteto, motivo ou "Buscando…" */
  aviso: string;
  imagem: string | null;
  fontes: FonteTela[];
}

const dataFonte = (iso?: string | null) => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase().replace(/\./g, "");
};

/** Linha de orcamento_itens -> o que a tela de estimativa desenha. Sem preço nunca vira número. */
export function itemParaTela(i: ItemLinha): ItemTela {
  const linha = linhasDocumento([i])[0];
  const fontes: FonteTela[] = (i.fontes ?? [])
    .slice()
    .sort((a, b) => a.preco_embalagem - b.preco_embalagem)
    .map((f) => ({
      loja: f.loja,
      dominio: f.dominio,
      url: hmm(f.url),
      preco: `${reais(f.preco_embalagem)}${f.embalagem || i.embalagem ? ` / ${f.embalagem || i.embalagem}` : ""}`,
      data: dataFonte(i.preco_data),
    }));
  const melhorLoja = fontes[0]?.loja;
  const nome = i.produto_normalizado || i.descricao;
  const unitario =
    i.preco_un_med != null && i.unidade_preco
      ? `${reais(i.preco_un_med)} / ${formatarUnidade(i.unidade_preco)}`
      : i.preco_emb_med != null
        ? `${reais(i.preco_emb_med)}${i.embalagem ? ` / ${i.embalagem}` : ""}`
        : "";

  let situacao: SituacaoItem;
  let aviso = "";
  if (linha) situacao = "precificado";
  else if (i.status === "buscando") (situacao = "buscando"), (aviso = "Buscando…");
  else if (i.status === "pendente_especificacao") (situacao = "pendente"), (aviso = i.pergunta || "Complete a especificação para ter preço.");
  else (situacao = "sem-preco"), (aviso = i.motivo || "Sem preço encontrado.");

  return {
    id: i.id,
    nome,
    detalhe: i.produto_normalizado && i.produto_normalizado !== i.descricao ? i.descricao : i.embalagem || "",
    loja: [melhorLoja, i.categoria].filter(Boolean).join(" · ") || (situacao === "precificado" ? "" : "Sem preço · excluído do subtotal"),
    quantidade: formatarQtd(i.quantidade, i.unidade),
    compra: i.qtd_embalagens && i.embalagem ? embalagens(i.qtd_embalagens, i.embalagem) : "",
    total: linha ? linha.total : null,
    unitario: linha ? unitario : "",
    situacao,
    aviso,
    imagem: hmm(i.imagem_url),
    fontes,
  };
}

/** Itens da lista: pendentes e sem preço no fim, na ordem em que o arquiteto os escreveu (Figma, tela 05). */
export function itensParaTela(itens: ItemLinha[]): ItemTela[] {
  const ordem = (t: ItemTela) => (t.situacao === "precificado" || t.situacao === "buscando" ? 0 : t.situacao === "sem-preco" ? 1 : 2);
  return itens
    .filter(entraNaConta)
    .map(itemParaTela)
    .map((t, i) => ({ t, i }))
    .sort((a, b) => ordem(a.t) - ordem(b.t) || a.i - b.i)
    .map(({ t }) => t);
}

/** "03 itens precificados" / "01 item pendente": dois dígitos, singular e plural (como no Figma). */
export const contagem = (n: number, um: string, varios: string) => `${String(n).padStart(2, "0")} ${n === 1 ? um : varios}`;

/** Título editorial: a última palavra vai em itálico com ponto ("Cozinha Planejada" + "Graças."). */
export function tituloEditorial(nome: string): { titulo: string; destaque: string } {
  const partes = nome.trim().split(/\s+/);
  const destaque = partes.pop() ?? "";
  return { titulo: partes.join(" "), destaque: `${destaque.replace(/[.]+$/, "")}.` };
}

export function mesAno(iso?: string | null): string {
  const d = iso ? new Date(iso) : new Date();
  const base = Number.isNaN(d.getTime()) ? new Date() : d;
  return base.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}
