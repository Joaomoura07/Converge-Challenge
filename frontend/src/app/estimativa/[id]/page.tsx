"use client";

// Estimativa de uma obra com dados reais: telas 05 (Materiais), 06 (Fontes) e 08 (Documento) do Figma.
// Mesmo layout e mesmas classes do protótipo em /estimativa; os dados vêm do useOrcamento(id).
import Link from "next/link";
import { use } from "react";
import { EstimativaView } from "@/components/resultado/EstimativaView";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import { useOrcamento } from "@/lib/orcamento/useOrcamento";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function EstimativaObra({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const valido = UUID.test(id);
  const { conexao, carregado, orcamento, itens, erro, recarregar } = useOrcamento(valido ? id : null);

  if (!valido) {
    return (
      <>
        <CabecalhoPagina trilha={[{ rotulo: "Estimativas", href: "/projetos" }, { rotulo: "Estimativa" }]} titulo="Código de orçamento" destaque="inválido." />
        <p role="alert">O endereço não traz um código de orçamento válido.</p>
        <Link href="/nova" className="sh-link">← Nova estimativa</Link>
      </>
    );
  }

  if (!orcamento) {
    return (
      <>
        <CabecalhoPagina trilha={[{ rotulo: "Estimativas", href: "/projetos" }, { rotulo: "Estimativa" }]} titulo="Estimativa" destaque="em preparo." />
        {conexao === "sem-configuracao" && (
          <p role="alert">
            Falta configurar o banco: defina <code>NEXT_PUBLIC_SUPABASE_URL</code> e <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> e recarregue.
          </p>
        )}
        {conexao === "erro-leitura" && (
          <p role="alert">
            Não foi possível ler o orçamento. {erro}{" "}
            <button type="button" className="sh-botao claro" onClick={recarregar}>Tentar de novo</button>
          </p>
        )}
        {conexao !== "sem-configuracao" && conexao !== "erro-leitura" && (
          <p role="status" aria-live="polite">{carregado ? "Este orçamento ainda não chegou ao servidor. Os itens aparecem aqui sozinhos." : "Carregando o orçamento…"}</p>
        )}
      </>
    );
  }

  return <EstimativaView orcamento={orcamento} itens={itens} />;
}
