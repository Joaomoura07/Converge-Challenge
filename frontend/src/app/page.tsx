import Link from "next/link";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import { PROJETOS, reais } from "@/lib/prototipo";

// Tela 01 · Projetos
export default function Projetos() {
  return (
    <>
      <CabecalhoPagina
        trilha={[{ rotulo: "Ateliê Linha" }, { rotulo: "Projetos" }]}
        etiqueta="Seu escritório · novembro 2026"
        titulo="Ideias em"
        destaque="andamento."
        apoio="Projetos, materiais e decisões, sem perder nada de vista."
        acao={
          <Link href="/nova" className="sh-botao">
            Nova estimativa <span aria-hidden="true">+</span>
          </Link>
        }
      />

      <p className="sh-apoio" style={{ marginBottom: 12 }}>
        <strong style={{ fontFamily: "var(--serif)", fontSize: 22, color: "var(--tinta)" }}>03</strong> projetos no escritório
        <span className="sh-aviso" style={{ float: "right" }}>
          01 revisão necessária
        </span>
      </p>

      <ul className="sh-lista-projetos">
        {PROJETOS.map((p) => (
          <li key={p.n}>
            <Link href={p.href} className="sh-projeto">
              <span className="num">{p.n}</span>
              <span>
                <span className="nome">{p.nome}</span>
                <small>{p.cliente}</small>
              </span>
              <span className="local">{p.local}</span>
              <span className={p.aviso ? "sh-aviso" : undefined}>{p.estado}</span>
              <span className="valor">{p.valor ? `${reais.format(p.valor)} ↗` : "Criar estimativa ↗"}</span>
            </Link>
          </li>
        ))}
      </ul>

      <section className="sh-vazio-chamada" aria-labelledby="chamada">
        <p className="sh-etiqueta">Do projeto à especificação</p>
        <h2 id="chamada">
          Mais tempo para <em>projetar.</em>
        </h2>
        <p className="sh-apoio">Cuidamos da busca de materiais. O arquiteto garante as referências e prepara a estimativa.</p>
      </section>
    </>
  );
}
