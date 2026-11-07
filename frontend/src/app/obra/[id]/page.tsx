"use client";

import Link from "next/link";
import { use } from "react";
import { reenviar, useEnvio } from "@/lib/envio/armazem";
import { EncaixeResultado } from "@/components/obra/EncaixeResultado";
import { ResultadoItens } from "@/components/orcamento/ResultadoItens";
import { CabecalhoPagina } from "@/components/shell/CabecalhoPagina";
import { useOrcamento, type Conexao } from "@/lib/orcamento/useOrcamento";
import "./obra.css";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const ROTULO_CONEXAO: Record<Conexao, string> = {
  "sem-configuracao": "Sem conexão configurada",
  conectando: "Conectando…",
  "ao-vivo": "Ao vivo",
  reconectando: "Reconectando…",
  "erro-leitura": "Falha na leitura",
};

// Esqueleto do resultado (etapa 07). Rota: /obra/[id]. O [id] é o UUID que a tela gerou ANTES do POST /orcamentos,
// então esta página pode abrir antes de o orçamento existir no banco ("aguardando o envio").
export default function Obra({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const valido = UUID.test(id);
  const { conexao, carregado, orcamento, itens, erro, recarregar } = useOrcamento(valido ? id : null);

  if (!valido) {
    return (
      <>
        <CabecalhoPagina trilha={[{ rotulo: "Projetos", href: "/" }, { rotulo: "Resultado" }]} titulo="Código de orçamento" destaque="inválido." />
        <p className="obra-bloco__texto" role="alert">
          O endereço não traz um código de orçamento válido. Volte e inicie a obra de novo.
        </p>
        <Link href="/nova" className="sh-link">← Nova estimativa</Link>
      </>
    );
  }

  const envio = useEnvio(valido ? id : null);
  const enviando = envio?.tipo === "enviando";
  const aguardando = carregado && !orcamento && !enviando && envio?.tipo !== "erro";

  return (
    <>
      <CabecalhoPagina
        trilha={[{ rotulo: "Projetos", href: "/" }, { rotulo: orcamento?.nome ?? "Orçamento" }, { rotulo: "Resultado" }]}
        etiqueta="Resultado"
        titulo={orcamento ? "Orçamento de" : "Orçamento"}
        destaque={orcamento?.nome ?? "em preparo."}
        apoio={
          <span className={`obra-conexao obra-conexao--${conexao}`} role="status" aria-live="polite">
            <span className="obra-conexao__ponto" aria-hidden="true" />
            {ROTULO_CONEXAO[conexao]}
          </span>
        }
      />

      {enviando && (
        <section className="obra-bloco" role="status" aria-live="polite">
          <h2 className="obra-bloco__titulo">Enviando e pesquisando preços…</h2>
          <p className="obra-bloco__texto">
            Os itens aparecem aqui sozinhos, um a um, enquanto a pesquisa roda. Pode levar alguns minutos: não feche esta
            página.
          </p>
        </section>
      )}

      {envio?.tipo === "erro" && (
        <section className="obra-bloco" role="alert">
          <h2 className="obra-bloco__titulo">
            {envio.erro.motivo === "validacao"
              ? "O servidor recusou a lista"
              : envio.erro.motivo === "conflito"
                ? "Este código já foi usado com outro conteúdo"
                : envio.erro.motivo === "config"
                  ? "O servidor não está pronto"
                  : "O envio não terminou"}
          </h2>
          <p className="obra-bloco__texto">{envio.erro.mensagem}</p>
          <div className="obra-acoes">
            {envio.erro.recuperavel && (
              <button type="button" className="sh-botao" onClick={() => void reenviar(id)}>
                Reenviar o mesmo pedido
              </button>
            )}
            <Link href={`/nova?retomar=${id}`} className="sh-link">
              ← Voltar e corrigir a lista
            </Link>
          </div>
        </section>
      )}

      {conexao === "sem-configuracao" && (
        <section className="obra-bloco" role="alert">
          <h2 className="obra-bloco__titulo">A conexão com o banco não está configurada</h2>
          <p className="obra-bloco__texto">
            Defina <code>NEXT_PUBLIC_SUPABASE_URL</code> e <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> (somente a chave
            pública) e recarregue a página.
          </p>
        </section>
      )}

      {conexao === "erro-leitura" && (
        <section className="obra-bloco" role="alert">
          <h2 className="obra-bloco__titulo">Não foi possível ler o orçamento</h2>
          <p className="obra-bloco__texto">{erro}</p>
          <button type="button" className="sh-botao" onClick={recarregar}>
            Tentar de novo
          </button>
        </section>
      )}

      {(conexao === "conectando" || (conexao !== "sem-configuracao" && !carregado && conexao !== "erro-leitura")) && (
        <p className="obra-bloco__texto" role="status" aria-live="polite">
          Carregando o orçamento…
        </p>
      )}

      {aguardando && (
        <section className="obra-bloco" role="status" aria-live="polite">
          <h2 className="obra-bloco__titulo">Aguardando o envio</h2>
          <p className="obra-bloco__texto">
            Este orçamento ainda não chegou ao servidor. Assim que o envio terminar de gravar, os itens aparecem aqui
            sozinhos. Código: <span className="obra-mono">{id}</span>
          </p>
        </section>
      )}

      {orcamento && (
        <>
          {orcamento.status_pesquisa === "falhou" && (
            <section className="obra-bloco" role="alert">
              <h2 className="obra-bloco__titulo">A pesquisa não terminou</h2>
              <p className="obra-bloco__texto">
                {orcamento.pesquisa_erro ?? "A pesquisa falhou."} O orçamento está salvo; reenvie o mesmo pedido para tentar de novo.
              </p>
            </section>
          )}

          {/* ENCAIXE DA B: a lista de itens ao vivo (ItemRow, cota de preço, Responder e Pesquisar de novo). */}
          <ResultadoItens itens={itens} />

          {/* ENCAIXE DA C: totais, "cabe ou não", frete, ganho de tempo e Exportar. */}
          <EncaixeResultado orcamento={orcamento} itens={itens} />
        </>
      )}
    </>
  );
}
