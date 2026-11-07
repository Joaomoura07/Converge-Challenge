// Três obras de exemplo (de docs/arquivos-teste). Passam pelo MESMO leitor dos uploads.

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
    descricao: "68 m², CSV do Excel em Windows-1252, separador ponto e vírgula",
    arquivo: "/exemplos/apto-boa-viagem.csv",
  },
  {
    id: "casa-terrea-aldeia",
    rotulo: "Casa térrea em Aldeia",
    descricao: "120 m², UTF-8 com marca de ordem, separador ponto e vírgula",
    arquivo: "/exemplos/casa-terrea-aldeia.csv",
  },
  {
    id: "escritorio-ilha-do-leite",
    rotulo: "Escritório na Ilha do Leite",
    descricao: "220 m², UTF-8, separador vírgula, cabeçalho em inglês",
    arquivo: "/exemplos/escritorio-ilha-do-leite.csv",
  },
];
