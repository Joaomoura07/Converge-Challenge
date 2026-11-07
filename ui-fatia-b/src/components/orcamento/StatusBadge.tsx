"use client";
// Status nunca só por cor: cor + ícone + texto (skills/04-ui-design.md, seção 2).

import type { StatusItem } from "./tipos";

const TEXTO: Record<StatusItem, string> = {
  buscando: "Pesquisando",
  definido: "Definido",
  pendente_especificacao: "Pendente de especificação",
  nao_encontrado: "Não encontrado",
  erro: "Erro na pesquisa",
};

function Icone({ status }: { status: StatusItem }) {
  const comum = { width: 14, height: 14, viewBox: "0 0 14 14", fill: "none", stroke: "currentColor",
                  strokeWidth: 1.6, "aria-hidden": true } as const;
  switch (status) {
    case "definido":
      return <svg {...comum}><path d="M2.5 7.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" /></svg>;
    case "pendente_especificacao":
      return <svg {...comum}><path d="M7 1.8l5.6 10H1.4z" strokeLinejoin="round" /><path d="M7 5.5v3M7 10.2v.1" strokeLinecap="round" /></svg>;
    case "nao_encontrado":
    case "erro":
      return <svg {...comum}><circle cx="7" cy="7" r="5.6" /><path d="M4.8 4.8l4.4 4.4M9.2 4.8l-4.4 4.4" strokeLinecap="round" /></svg>;
    default:
      return <svg {...comum}><circle cx="7" cy="7" r="5.6" strokeDasharray="2 2" /></svg>;
  }
}

export function StatusBadge({ status }: { status: StatusItem }) {
  return (
    <span className={`orc-status orc-status--${status}`}>
      <Icone status={status} />
      {TEXTO[status]}
    </span>
  );
}
