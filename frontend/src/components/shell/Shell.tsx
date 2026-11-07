"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/** Marca da OrçaAI: a orca (logo do time), traço marfim sobre o fundo escuro. */
export function MarcaOrcaAI({ tamanho = 34 }: { tamanho?: number }) {
  return <Image src="/marca/orca.png" alt="" aria-hidden="true" width={tamanho} height={tamanho} priority unoptimized />;
}

const LINKS = [
  { href: "/", rotulo: "Início" },
  { href: "/projetos", rotulo: "Projetos" },
  { href: "/nova", rotulo: "Nova estimativa" },
  { href: "/#como-funciona", rotulo: "Como funciona" },
];

/** Casca do site (protótipo OrçaAI): barra no topo, transparente sobre o hero da página inicial
 *  e fosca (desfoque) ao rolar ou dentro do app. */
export function Shell({ children }: { children: React.ReactNode }) {
  const caminho = usePathname() ?? "/";
  const site = caminho === "/";
  const [rolou, setRolou] = useState(false);

  useEffect(() => {
    if (!site) return;
    const aoRolar = () => setRolou(window.scrollY > 24);
    aoRolar();
    window.addEventListener("scroll", aoRolar, { passive: true });
    return () => window.removeEventListener("scroll", aoRolar);
  }, [site]);

  const atual = (href: string) =>
    href === "/"
      ? caminho === "/"
      : href === "/projetos"
      ? caminho.startsWith("/projetos") || caminho.startsWith("/obra") || caminho.startsWith("/estimativa")
      : href === "/nova"
        ? caminho.startsWith("/nova") || caminho.startsWith("/revisar") || caminho.startsWith("/pesquisa")
        : false;

  return (
    <div className="sh-app">
      <header className="oa-nav" data-modo={site ? "site" : "app"} data-rolou={rolou}>
        <div className="oa-nav__dentro">
          <Link href="/" className="oa-marca" aria-label="OrçaAI, página inicial">
            <MarcaOrcaAI />
            <span>
              Orça<b>AI</b>
            </span>
          </Link>
          <nav aria-label="Principal" style={{ display: "contents" }}>
            <ul className="oa-links">
              {LINKS.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} aria-current={atual(l.href) ? "page" : undefined}>
                    {l.rotulo}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="oa-direita">
            {site ? (
              <>
                <Link href="/projetos" className="oa-botao oa-botao--fantasma oa-botao--pequeno">
                  Entrar
                </Link>
                <Link href="/nova" className="oa-botao oa-botao--principal oa-botao--pequeno">
                  Criar estimativa
                </Link>
              </>
            ) : (
              <>
                <span className="oa-tag">Protótipo, dados fictícios</span>
                <span className="oa-escritorio">
                  <span>Ateliê Linha</span>
                  <span className="iniciais" aria-hidden="true">
                    AL
                  </span>
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      {site ? (
        children
      ) : (
        <div className="sh-principal">
          {/* div, não main: algumas telas (Caderno, prévia B) já têm o próprio <main> */}
          <div className="sh-conteudo">{children}</div>
        </div>
      )}

      <footer className="oa-rodape">
        <div className="oa-rodape__dentro">
          <span>OrçaAI, protótipo criado no Converge Challenge, Recife, novembro de 2026.</span>
          <span>Preços pesquisados em lojas online, sempre com a fonte. Confirme com a loja antes de comprar.</span>
        </div>
      </footer>
    </div>
  );
}
