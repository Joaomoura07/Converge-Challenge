// Passos da /demo: mostram ao jurado onde ele está (1 Obra → 2 Arquivo ou digitar → 3 Revisar → 4 Enviar para a IA).
// O passo atual é calculado pelo Caderno a partir do estado real da tela, não por tempo.

export type PassoDemo = 1 | 2 | 3 | 4;

const PASSOS: { n: PassoDemo; titulo: string; dica: string }[] = [
  { n: 1, titulo: "Obra", dica: "Nome, CEP e orçamento do cliente" },
  { n: 2, titulo: "Arquivo ou digitar", dica: "Baixe um exemplo e arraste para a área" },
  { n: 3, titulo: "Revisar", dica: "Confira os avisos e aceite o que fizer sentido" },
  { n: 4, titulo: "Enviar para a IA", dica: "Os preços chegam ao vivo, com a loja" },
];

export function PassosDemo({ atual }: { atual: PassoDemo }) {
  return (
    <ol className="demo-passos" aria-label="Passos da demonstração">
      {PASSOS.map((p) => (
        <li key={p.n} data-estado={p.n < atual ? "feito" : p.n === atual ? "atual" : "depois"}
            aria-current={p.n === atual ? "step" : undefined}>
          <span className="n" aria-hidden="true">{p.n < atual ? "✓" : p.n}</span>
          <span className="texto">
            <strong>{p.titulo}</strong>
            <small>{p.dica}</small>
          </span>
        </li>
      ))}
    </ol>
  );
}
