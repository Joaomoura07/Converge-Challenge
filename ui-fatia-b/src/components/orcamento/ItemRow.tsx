"use client";
// Uma linha do resultado ao vivo (skills/04-ui-design.md, seção 3.3): imagem, produto, frase de compra,
// cota de preço, confiança, lojas e, quando pendente, a pergunta do agente com "Responder".

import { useEffect, useRef, useState, type FormEvent } from "react";
import { CONFIANCA, embalagens, quantidade, reais } from "./formato";
import { PriceDimension } from "./PriceDimension";
import { StatusBadge } from "./StatusBadge";
import type { ItemOrcamento } from "./tipos";

interface Props {
  item: ItemOrcamento;
  /** Resposta do arquiteto à pergunta → o backend chama repesquisar_item(item_id, nova_descricao). */
  onResponder?: (item: ItemOrcamento, especificacao: string) => void;
  /** Botão "Pesquisar de novo" → repesquisar_item(item_id). */
  onPesquisarDeNovo?: (item: ItemOrcamento) => void;
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

export function ItemRow({ item, onResponder, onPesquisarDeNovo }: Props) {
  const carregando = item.status === "buscando";
  const chegou = useChegou(item.status);
  const [respondendo, setRespondendo] = useState(false);
  const [resposta, setResposta] = useState("");
  const nome = item.produto_normalizado || item.descricao;
  const lojas = item.fontes ?? [];
  // "1 un → 1 unidade" não informa nada: a frase de compra só aparece quando a embalagem muda a conta
  const porUnidade = !item.embalagem || /^unidade$/i.test(item.embalagem.trim());
  const compra = item.qtd_embalagens && item.embalagem && !porUnidade ? embalagens(item.qtd_embalagens, item.embalagem) : null;

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (resposta.trim().length >= 3) {
      onResponder?.(item, resposta.trim());
      setRespondendo(false);
    }
  }

  return (
    <article className={`orc-item orc-item--${item.status}${chegou ? " orc-item--chegou" : ""}`} aria-busy={carregando}>
      <div className={`orc-item__imagem${item.imagem_url && !carregando ? "" : " orc-item__imagem--hachura"}`}>
        {item.imagem_url && !carregando && <img src={item.imagem_url} alt={nome} loading="lazy" width={56} height={56} />}
      </div>

      <div className="orc-item__corpo">
        <div className="orc-item__titulo">
          <h3>{nome}</h3>
          {!carregando && <StatusBadge status={item.status} />}
        </div>
        <p className="orc-item__compra">
          {quantidade(item.quantidade, item.unidade)}
          {compra && <> → <strong>{compra}</strong></>}
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
              <button type="button" className="orc-botao orc-botao--principal" onClick={() => setRespondendo(true)}>Responder</button>
            )}
          </div>
        )}

        {(item.status === "nao_encontrado" || item.status === "erro") && (
          <div className="orc-item__falha">
            <p>{item.motivo}</p>
            <button type="button" className="orc-botao" onClick={() => onPesquisarDeNovo?.(item)}>Pesquisar de novo</button>
          </div>
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
            {item.confianca && <span>{CONFIANCA[item.confianca]}</span>}
            <span>{lojas.length === 1 ? "1 loja" : `${lojas.length} lojas`}</span>
            {item.preco_un_med != null && item.unidade_preco && (
              <span>{reais(item.preco_un_med)}/{item.unidade_preco === "m2" ? "m²" : item.unidade_preco}</span>
            )}
          </p>
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
              <a href={f.url} target="_blank" rel="noopener noreferrer">{f.loja}</a>
              <span>{reais(f.preco_embalagem)}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
