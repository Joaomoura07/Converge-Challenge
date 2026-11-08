// Regras editáveis: nome de layer ou de bloco -> descrição genérica e categoria.
// Um DXF quase nunca traz a especificação do produto: a descrição sai genérica e a revisão E1/E2 pergunta o resto.

export type RegraDxf = { padrao: RegExp; descricao: string; categoria: string };

export const REGRAS_DXF: RegraDxf[] = [
  { padrao: /porta|door|\bpt\b/i, descricao: "Porta", categoria: "Esquadrias" },
  { padrao: /janela|window|\bjn\b/i, descricao: "Janela", categoria: "Esquadrias" },
  { padrao: /piso|floor|ceramic|porcelan/i, descricao: "Piso", categoria: "Revestimentos" },
  { padrao: /parede|wall|alvenaria/i, descricao: "Parede", categoria: "Alvenaria" },
  { padrao: /forro|ceiling/i, descricao: "Forro", categoria: "Forro" },
  { padrao: /laje|slab/i, descricao: "Laje", categoria: "Estrutura" },
  { padrao: /rodape|rodapé|skirting/i, descricao: "Rodapé", categoria: "Revestimentos" },
  { padrao: /el[eé]tric|tomada|eletr/i, descricao: "Ponto elétrico", categoria: "Elétrica" },
  { padrao: /hidr|tubo|pipe/i, descricao: "Tubulação", categoria: "Hidráulica" },
];

export function mapearNome(nome: string): { descricao: string; categoria: string | null; conhecido: boolean } {
  const r = REGRAS_DXF.find((x) => x.padrao.test(nome));
  return r ? { descricao: r.descricao, categoria: r.categoria, conhecido: true } : { descricao: nome, categoria: null, conhecido: false };
}
