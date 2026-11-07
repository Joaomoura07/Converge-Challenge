"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ICONE_PROJETOS = (
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <rect x="1.5" y="3.5" width="13" height="9" rx="1" />
  </svg>
);
const ICONE_ESTIMATIVA = (
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <path d="M3 3h10M3 6.5h10M3 10h10M3 13h6" />
  </svg>
);

/** Estrutura do Figma: trilho lateral + barra do escritório + conteúdo. */
export function Shell({ children }: { children: React.ReactNode }) {
  const caminho = usePathname() ?? "/";
  const emProjetos = caminho === "/";
  return (
    <div className="sh-app">
      <nav className="sh-trilho" aria-label="Principal">
        <Link href="/" className="sh-logo" aria-label="Orça — início">
          o
        </Link>
        <Link href="/" className="sh-nav-item" aria-current={emProjetos ? "page" : undefined}>
          {ICONE_PROJETOS}
          Projetos
        </Link>
        <Link href="/nova" className="sh-nav-item" aria-current={!emProjetos ? "page" : undefined}>
          {ICONE_ESTIMATIVA}
          Estimativa
        </Link>
        <span className="sh-iniciais" aria-hidden="true">
          AL
        </span>
      </nav>
      <div className="sh-principal">
        <header className="sh-barra">
          <span>
            <strong>Ateliê Linha</strong>Arquitetura &amp; interiores
          </span>
          <span className="sh-prototipo">Protótipo · dados fictícios</span>
        </header>
        <div className="sh-conteudo">{children}</div>
      </div>
    </div>
  );
}
