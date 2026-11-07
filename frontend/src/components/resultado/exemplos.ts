// Dados FICTÍCIOS no formato real da API, só para a página de prévia (/previa-c) e para testes visuais.
import type { ItemLinha, Orcamento } from "@/lib/orcamento/tipos";

let n = 0;
const base = { orcamento_id: "exemplo", atualizado_em: "2026-11-07T18:00:00Z" } as const;
const fonte = (loja: string, dominio: string, p: number) => ({ loja, dominio, url: `https://www.${dominio}/p/exemplo`, preco_embalagem: p });
const def = (descricao: string, emb: string, qtd: number, med: number, fontes: ReturnType<typeof fonte>[]): ItemLinha => ({
  ...base, id: `e${++n}`, linha: n, descricao, status: "definido", embalagem: emb, qtd_embalagens: qtd,
  preco_emb_min: Math.min(...fontes.map((f) => f.preco_embalagem)), preco_emb_med: med,
  preco_emb_max: Math.max(...fontes.map((f) => f.preco_embalagem)), confianca: "alta", fontes,
});

const ITENS_BASE: ItemLinha[] = [
  def("Porcelanato Portobello Cimento 90x90", "caixa 1,62 m²", 33, 118.9, [fonte("Telhanorte", "telhanorte.com.br", 112.5), fonte("Leroy Merlin", "leroymerlin.com.br", 118.9), fonte("Obramax", "obramax.com.br", 121)]),
  def("Tinta acrílica Coral Decora Cinza Urbano", "lata 18 L", 2, 499, [fonte("Leroy Merlin", "leroymerlin.com.br", 489.9), fonte("C&C", "cec.com.br", 512)]),
  def("Argamassa colante AC-III", "saco 20 kg", 15, 36.9, [fonte("Mercado Livre", "mercadolivre.com.br", 34.9), fonte("Leroy Merlin", "leroymerlin.com.br", 36.9)]),
  def("Rejunte Quartzolit cinza platina", "saco 5 kg", 5, 49.9, [fonte("Telhanorte", "telhanorte.com.br", 47), fonte("Amazon", "amazon.com.br", 49.9)]),
  { ...base, id: "ep", linha: 5, descricao: "Tinta vermelha para a parede da copa", status: "pendente_especificacao", pergunta: "Qual acabamento e litragem da tinta vermelha?" },
];

const sem = (descricao: string, status: ItemLinha["status"]): ItemLinha => ({ ...base, id: `s${++n}`, linha: 90 + n, descricao, status });

export const orcamentoBase = (p: Partial<Orcamento>): Orcamento => ({
  id: "11111111-1111-4111-8111-111111111111", nome: "Cozinha Planejada — Graças", cep: "52011050", orcamento_cliente: 9000,
  status_pesquisa: "concluida", pesquisa_iniciada_em: "2026-11-07T17:00:00Z", pesquisa_concluida_em: "2026-11-07T17:00:28Z",
  pesquisa_erro: null, qtd_itens: 5, custo_usd: 0.05, tempo_ms: 28000, trace_url: null, created_at: "", atualizado_em: "",
  logistica: {
    estrategia: "dividir", frete_total: 0, total_produtos: 5988.5, total: 5988.5, economia_estimada: 0, itens_sem_loja: [],
    lojas: [{ id: "telhanorte.com.br", nome: "Telhanorte", itens: [0, 3], subtotal: 3961.5, frete: 0 }, { id: "mercadolivre.com.br", nome: "Mercado Livre", itens: [2], subtotal: 523.5, frete: 0 }, { id: "leroymerlin.com.br", nome: "Leroy Merlin", itens: [1], subtotal: 979.8, frete: 0 }],
  },
  viabilidade: { orcamento_cliente: 9000, total_min: 5700, total_med: 6021.5, total_max: 6410, cabe: true, cabe_no_minimo: true, diferenca: -2978.5, completo: true,
    resumo: "Cabe: total estimado R$ 6.021,50 para orçamento de R$ 9.000,00 (sobram R$ 2.978,50).", itens_sem_preco: [], sugestoes: [] },
  ganho: { resumo: "À mão: ~1 h 30 min. Aqui: 28 s. Custo de IA: R$ 0,27", reducao_pct: 99.5 },
  ...p,
});

export const CENARIOS: Record<string, { rotulo: string; orcamento: Orcamento; itens: ItemLinha[] }> = {
  cabe: { rotulo: "Cabe no orçamento", orcamento: orcamentoBase({}), itens: ITENS_BASE },
  "nao-cabe": {
    rotulo: "Não cabe",
    itens: ITENS_BASE,
    orcamento: orcamentoBase({
      orcamento_cliente: 4500,
      viabilidade: { orcamento_cliente: 4500, total_min: 5700, total_med: 6021.5, total_max: 6410, cabe: false, cabe_no_minimo: false, diferenca: 1521.5, completo: true,
        resumo: "Não cabe: faltam R$ 1.521,50 (média R$ 6.021,50 para orçamento de R$ 4.500,00).", itens_sem_preco: [],
        sugestoes: [
          { tipo: "preco_minimo", texto: "Fechar os 3 itens de maior variação de preço na loja mais barata economiza até R$ 321,20.", economia: 321.2 },
          { tipo: "pendencias", texto: "1 item ainda sem especificação entra com valor estimado: defini-lo pode mudar o total." },
        ] },
    }),
  },
  parcial: {
    rotulo: "Itens sem preço",
    itens: [...ITENS_BASE, sem("Painel ripado freijó sob medida", "nao_encontrado"), sem("Bancada de granito Branco Itaúnas", "buscando")],
    orcamento: orcamentoBase({
      viabilidade: { orcamento_cliente: 9000, total_min: 5700, total_med: 6021.5, total_max: 6410, cabe: true, cabe_no_minimo: true, diferenca: -2978.5, completo: false,
        resumo: "Ainda não dá para afirmar: 2 itens ainda sem preço ficaram fora do total. Até agora cabe: total estimado R$ 6.021,50 para orçamento de R$ 9.000,00.", itens_sem_preco: [5, 6], sugestoes: [] },
    }),
  },
};
