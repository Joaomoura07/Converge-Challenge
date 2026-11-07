// Dados FICTÍCIOS só para as telas-base copiadas do Figma (projetos, estimativa, fontes).
// Serão trocados pelos dados reais (useOrcamento) quando a integração existir.

export const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export const PROJETOS = [
  { n: "001", nome: "Residência Aurora", cliente: "Clara & Miguel", local: "Recife, PE", estado: "Revisão necessária", aviso: true, valor: 7020.2, href: "/estimativa" },
  { n: "002", nome: "Apartamento Jardim", cliente: "Federica Lima", local: "Olinda, PE", estado: "Nova lista", aviso: false, valor: null, href: "/nova" },
  { n: "003", nome: "Estúdio Boa Vista", cliente: "Rafael Dias", local: "Recife, PE", estado: "Nova lista", aviso: false, valor: null, href: "/nova" },
];

export type MaterialRevisao = { id: string; material: string; especificacao: string; quantidade: string; unidade: string };

export const MATERIAIS_REVISAO: MaterialRevisao[] = [
  { id: "m1", material: "Porcelanato", especificacao: "Acetinado, 60 × 60 cm, bege", quantidade: "60", unidade: "m²" },
  { id: "m2", material: "Tinta acrílica", especificacao: "Fosca, branco neve, 18 L", quantidade: "3", unidade: "un" },
  { id: "m3", material: "Spot LED", especificacao: "Embutir, 7 W, 3000 K", quantidade: "8", unidade: "un" },
  { id: "m4", material: "Torneira para banheiro", especificacao: "", quantidade: "1", unidade: "un" },
];

export const PASSOS_PESQUISA = [
  { t: "Interpretar a lista", d: "Reconhecer materiais, unidades e categorias." },
  { t: "Encontrar referências", d: "Consultar ofertas de conjunto de ofertas físicas." },
  { t: "Comparar especificações", d: "Verificar correspondência e unidade de venda." },
  { t: "Organizar a estimativa", d: "Separar valores confirmados e itens pendentes." },
];

export type ItemEstimativa = {
  id: string;
  nome: string;
  detalhe: string;
  loja: string;
  quantidade: string;
  total: number | null;
  unitario: string;
  pendente?: boolean;
  fontes: { loja: string; dominio: string; preco: string }[];
};

export const ITENS_ESTIMATIVA: ItemEstimativa[] = [
  { id: "e1", nome: "Porcelanato", detalhe: "Acetinado, 60 × 60 cm, bege", loja: "Casa Pontes · Revestimentos", quantidade: "60 m²", total: 5394, unitario: "R$ 89,90 / m²",
    fontes: [{ loja: "Casa Pontes", dominio: "casapontes.example", preco: "R$ 89,90 / m²" }, { loja: "Revest Norte", dominio: "revestnorte.example", preco: "R$ 94,50 / m²" }] },
  { id: "e2", nome: "Tinta acrílica", detalhe: "Fosca, branco neve, 18 L", loja: "Cor & Cia · Pintura", quantidade: "3 un", total: 987, unitario: "R$ 329,00 / lata",
    fontes: [{ loja: "Cor & Cia", dominio: "corecia.example", preco: "R$ 329,00 / lata" }] },
  { id: "e3", nome: "Spot LED", detalhe: "Embutir, 7 W, 3000 K", loja: "Luzes Materiais · Iluminação", quantidade: "8 un", total: 639.2, unitario: "R$ 79,90 / un",
    fontes: [{ loja: "Luzes Materiais", dominio: "luzesmateriais.example", preco: "R$ 79,90 / un" }] },
  { id: "e4", nome: "Torneira para banheiro", detalhe: "Modelo e acabamento em aberto", loja: "Sem preço · excluído do subtotal", quantidade: "1 un", total: null, unitario: "", pendente: true, fontes: [] },
];

export const SUBTOTAL = ITENS_ESTIMATIVA.reduce((s, i) => s + (i.total ?? 0), 0);
