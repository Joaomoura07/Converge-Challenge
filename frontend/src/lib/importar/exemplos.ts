// Três listas sintéticas de cinco itens. Passam pelo MESMO leitor dos uploads.

export type Exemplo = {
  id: string;
  rotulo: string;
  descricao: string;
  arquivo: string; // em frontend/public/exemplos
};

export const EXEMPLOS: Exemplo[] = [
  {
    id: "apto-boa-viagem",
    rotulo: "Apartamento Boa Viagem",
    descricao: "5 materiais especificados para conferir fontes, medidas e embalagens",
    arquivo: "/exemplos/demo/teste_1.csv",
  },
  {
    id: "casa-terrea-aldeia",
    rotulo: "Reforma em Casa Forte",
    descricao: "5 materiais para corrigir uma unidade, revisar complementos e especificar a tinta",
    arquivo: "/exemplos/demo/teste_2.csv",
  },
  {
    id: "escritorio-ilha-do-leite",
    rotulo: "Escritório na Ilha do Leite",
    descricao: "5 tipos de componente; confira peças, sacos e latas na lista de compra",
    arquivo: "/exemplos/demo/componentes.csv",
  },
];
