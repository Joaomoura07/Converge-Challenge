"use client";
// Uma linha do resultado ao vivo (skills/04-ui-design.md, seção 3.3): imagem, produto, frase de compra,
// cota de preço, confiança, lojas e, quando pendente, a pergunta do agente com "Responder".

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { OBJETIVOS, distanciaDaLoja, embalagens, quantidade, reais } from "./formato";
import { PriceDimension } from "./PriceDimension";
import { StatusBadge } from "./StatusBadge";
import type { ItemOrcamento, Objetivo } from "./tipos";

interface Props {
  item: ItemOrcamento;
  /** Resposta do arquiteto à pergunta → o backend chama repesquisar_item(item_id, nova_descricao). */
  onResponder?: (item: ItemOrcamento, especificacao: string) => void;
  /** "Pesquisar de novo" → "O mesmo produto" → repesquisar_item(item_id). */
  onPesquisarDeNovo?: (item: ItemOrcamento) => void;
  /** "Pesquisar de novo" → maior qualidade / menor preço / semelhante → repesquisar_item(item_id, objetivo). */
  onPesquisarAlternativa?: (item: ItemOrcamento, objetivo: Objetivo) => void;
  /** Item pendente → "Usar a média mesmo assim" → repesquisar_item(item_id, aceitar_media): sem marca, fica a média. */
  onAceitarMedia?: (item: ItemOrcamento) => void;
}

/** Botão "Pesquisar de novo" que abre as opções. Nada muda sem o clique do arquiteto numa delas. */
function PesquisarDeNovo({ item, onMesmo, onAlternativa }: {
  item: ItemOrcamento;
  onMesmo?: (item: ItemOrcamento) => void;
  onAlternativa?: (item: ItemOrcamento, objetivo: Objetivo) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const botao = useRef<HTMLButtonElement>(null);
  const idOpcoes = `repesquisa-${item.id}`;

  function fechar() {
    setAberto(false);
    botao.current?.focus();
  }

  function escolher(acao: () => void) {
    setAberto(false);
    acao();
  }

  function teclado(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      fechar();
    }
  }

  return (
    <div className="orc-repesquisa" onKeyDown={teclado}>
      <button ref={botao} type="button" className="orc-botao" aria-expanded={aberto} aria-controls={idOpcoes}
              onClick={() => setAberto((a) => !a)}>
        Pesquisar de novo
      </button>
      {aberto && (
        <div id={idOpcoes} role="group" aria-label="Pesquisar de novo buscando" className="orc-repesquisa__opcoes">
          <button type="button" className="orc-botao" autoFocus onClick={() => escolher(() => onMesmo?.(item))}
                  title="Atualiza o preço do mesmo produto">
            O mesmo produto
          </button>
          {onAlternativa && OBJETIVOS.map(({ objetivo, rotulo, dica }) => (
            <button key={objetivo} type="button" className="orc-botao" title={dica}
                    onClick={() => escolher(() => onAlternativa(item, objetivo))}>
              {rotulo}
            </button>
          ))}
          <button type="button" className="orc-botao orc-botao--discreto" onClick={fechar}>Cancelar</button>
        </div>
      )}
    </div>
  );
}

/** Fica true por 1,3 s quando o item sai de "buscando": é o único momento de animação da tela. */
function useChegou(status: ItemOrcamento["status"]) {
  const anterior = useRef(status);
  const [chegou, setChegou] = useState(false);
  useEffect(() => {
    if (anterior.current === "buscando" && status !== "buscando") setChegou(true);
    anterior.current = status;
  }, [status]);
  // timer num efeito separado: no StrictMode o efeito roda 2×, e o timer precisa sobreviver a isso
  useEffect(() => {
    if (!chegou) return;
    const t = setTimeout(() => setChegou(false), 1300);
    return () => clearTimeout(t);
  }, [chegou]);
  return chegou;
}

/** Link que abre no Google (página do Shopping) e não na loja: a tela mostra a loja sem link (08/11). */
function abreNoGoogle(f: { dominio: string; url: string }): boolean {
  if (f.dominio === "google.com") return true;
  try {
    return /(^|\.)google\./.test(new URL(f.url).hostname);
  } catch {
    return true;   // link inválido também não vira link
  }
}

export function ItemRow({ item, onResponder, onPesquisarDeNovo, onPesquisarAlternativa, onAceitarMedia }: Props) {
  const carregando = item.status === "buscando";
  const chegou = useChegou(item.status);
  const [respondendo, setRespondendo] = useState(false);
  const [resposta, setResposta] = useState("");
  const nome = item.produto_normalizado || item.descricao;
  const lojas = item.fontes ?? [];
  // Foto que não carrega (link quebrado, bloqueio) volta para a hachura cinza em vez do ícone de imagem quebrada.
  const [fotoFalhou, setFotoFalhou] = useState(false);
  const temFoto = !!item.imagem_url && !carregando && !fotoFalhou;
  // "1 un → 1 unidade" não informa nada: a frase de compra só aparece quando a embalagem muda a conta
  const porUnidade = !item.embalagem || /^unidade$/i.test(item.embalagem.trim());
  const compra = item.qtd_embalagens && item.embalagem && !porUnidade ? embalagens(item.qtd_embalagens, item.embalagem) : null;
  // Total do item: sem ele, "médio R$ 95,00 por kit 50" para 200 folhas parecia o preço das 200 (relato de 08/11).
  const total = item.qtd_embalagens && item.preco_emb_med != null ? item.qtd_embalagens * item.preco_emb_med : null;

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (resposta.trim().length >= 3) {
      onResponder?.(item, resposta.trim());
      setRespondendo(false);
    }
  }

  return (
    <article className={`orc-item orc-item--${item.status}${chegou ? " orc-item--chegou" : ""}`} aria-busy={carregando}>
      <div className={`orc-item__imagem${temFoto ? "" : " orc-item__imagem--hachura"}`}>
        {temFoto && <img src={item.imagem_url as string} alt={nome} loading="lazy" width={56} height={56}
                         referrerPolicy="no-referrer" onError={() => setFotoFalhou(true)} />}
      </div>

      <div className="orc-item__corpo">
        <div className="orc-item__titulo">
          <h3>{nome}</h3>
          {!carregando && <StatusBadge status={item.status} />}
        </div>
        <p className="orc-item__compra">
          {quantidade(item.quantidade, item.unidade)}
          {compra && <> → <strong>{compra}</strong></>}
          {total != null && !carregando && (
            <span className="orc-item__total">
              {" · "}total {item.estimativa ? "≈ " : ""}<strong>{reais(total)}</strong>
              {item.qtd_embalagens && item.qtd_embalagens > 1 ? ` (${item.qtd_embalagens} × ${reais(item.preco_emb_med as number)})` : ""}
            </span>
          )}
        </p>
        {item.premissa && !carregando && <p className="orc-item__premissa">Conta: {item.premissa}</p>}

        {item.status === "pendente_especificacao" && item.pergunta && (
          <div className="orc-item__pergunta">
            <p>{item.pergunta}</p>
            {respondendo ? (
              <form onSubmit={enviar} className="orc-item__resposta">
                <label className="orc-visivel-so-leitor" htmlFor={`resp-${item.id}`}>Especificação do item</label>
                <input id={`resp-${item.id}`} autoFocus required minLength={3} value={resposta}
                       onChange={(e) => setResposta(e.target.value)}
                       placeholder="Ex.: Suvinil Fosco Completo, Vermelho Cardinal, 3,6 L" />
                <button type="submit" className="orc-botao orc-botao--principal">Enviar resposta</button>
                <button type="button" className="orc-botao" onClick={() => setRespondendo(false)}>Cancelar</button>
              </form>
            ) : (
              <div className="orc-item__acoes">
                <button type="button" className="orc-botao orc-botao--principal" onClick={() => setRespondendo(true)}>Responder</button>
                {onAceitarMedia && item.preco_emb_med != null && (
                  <button type="button" className="orc-botao" onClick={() => onAceitarMedia(item)}
                          title="Não especifica marca e modelo: o item fica com a média de produtos parecidos, como estimativa">
                    Usar a média mesmo assim
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {(item.status === "nao_encontrado" || item.status === "erro") ? (
          <div className="orc-item__falha">
            <p>{item.motivo}</p>
            <PesquisarDeNovo item={item} onMesmo={onPesquisarDeNovo} onAlternativa={onPesquisarAlternativa} />
          </div>
        ) : !carregando && (
          <PesquisarDeNovo item={item} onMesmo={onPesquisarDeNovo} onAlternativa={onPesquisarAlternativa} />
        )}
      </div>

      <div className="orc-item__preco">
        {item.status === "nao_encontrado" || item.status === "erro" ? null : (
          <PriceDimension min={item.preco_emb_min} med={item.preco_emb_med} max={item.preco_emb_max}
                          carregando={carregando} chegou={chegou}
                          rotulo={item.embalagem && !carregando ? `por ${item.embalagem.replace(/(\d)\s*m²/, "$1 m²")}` : undefined} />
        )}
        {!carregando && item.preco_emb_med != null && (
          <p className="orc-item__confianca">
            {item.estimativa && <span className="orc-item__estimativa">Estimativa</span>}
            <span>{lojas.length === 1 ? "1 loja" : `${lojas.length} lojas`}</span>
            {item.preco_un_med != null && item.unidade_preco && (
              <span>{reais(item.preco_un_med)}/{item.unidade_preco === "m2" ? "m²" : item.unidade_preco}</span>
            )}
          </p>
        )}
        {!carregando && item.preco_emb_med != null && (
          <p className="orc-item__dica">Média dos preços encontrados para o que você pediu. Quanto mais especificações (marca, modelo, medida), melhor a pesquisa.</p>
        )}
        {!carregando && item.status === "definido" && item.motivo && <p className="orc-item__aviso">{item.motivo}</p>}
        {!carregando && (item.iteracoes ?? 0) > 0 && (
          <p className="orc-item__agente">A IA refez a busca {item.iteracoes === 1 ? "1 vez" : `${item.iteracoes} vezes`}</p>
        )}
      </div>

      {lojas.length > 0 && !carregando && (
        <ul className="orc-item__lojas" aria-label="Lojas onde o preço foi encontrado">
          {lojas.map((f) => (
            <li key={f.url}>
              {abreNoGoogle(f) ? (
                // O Shopping só entrega o link da página do produto NO GOOGLE, não o da loja: mostrar a loja como link
                // levava o usuário a uma página do Google achando que era o site dela (medido em 08/11).
                <>
                  <span>{f.loja}</span>
                  <span className="orc-item__google" title="Preço do Google Shopping. O link da loja não está disponível">
                    preço do Google
                  </span>
                </>
              ) : (
                <a href={f.url} target="_blank" rel="noopener noreferrer">{f.loja}</a>
              )}
              {(f.perto_da_obra || distanciaDaLoja(f.distancia_km)) && (
                <span className="orc-item__perto" title={f.endereco ?? undefined}>
                  perto da obra{distanciaDaLoja(f.distancia_km) ? ` · ${distanciaDaLoja(f.distancia_km)}` : ""}
                </span>
              )}
              {f.endereco && <span className="orc-item__endereco">{f.endereco}</span>}
              {/* o preço do anúncio (o mesmo que aparece ao clicar), com a embalagem quando ela é outra */}
              <span>
                {reais(f.preco_anunciado ?? f.preco_embalagem)}
                {f.preco_anunciado != null && f.embalagem_anunciada && f.embalagem_anunciada !== f.embalagem
                  ? ` · ${f.embalagem_anunciada}`
                  : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
