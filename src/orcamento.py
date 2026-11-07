"""Fatia B no banco: pesquisa um orçamento inteiro e grava cada item no Supabase assim que fica pronto
(o Realtime leva para a tela). Contrato combinado com a fatia A (SQL único):

orcamentos:      status_pesquisa (pendente | pesquisando | concluida | falhou), pesquisa_iniciada_em,
                 pesquisa_concluida_em, pesquisa_erro
orcamento_itens: a B LÊ  id, orcamento_id, descricao, quantidade, unidade, categoria, classificacao, status
                 a B GRAVA os campos de ResultadoItem (src/modelos.py) + atualizado_em

Uso pela fatia A, na MESMA requisição do POST /orcamentos (a Vercel encerra o que roda depois da resposta):
    await pesquisar_orcamento(orcamento_id)
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Protocol

from langfuse import observe, propagate_attributes

from .modelos import ItemEntrada, ResultadoItem
from .pesquisa import pesquisar_item, pesquisar_itens

logger = logging.getLogger(__name__)

ORCAMENTOS, ITENS = "orcamentos", "orcamento_itens"
COLUNAS_LIDAS = ["id", "orcamento_id", "descricao", "quantidade", "unidade", "categoria", "classificacao", "status"]
COLUNAS_GRAVADAS = [c for c in ResultadoItem.model_fields if c != "item_id"] + ["atualizado_em"]
JANELA_TRAVADO = timedelta(minutes=3)   # execução morta pela Vercel no meio libera o orçamento depois disso
# Ganchos da fatia C, chamados no fim: (módulo, função). Ausentes = só registra no log.
GANCHOS_FIM = [("src.logistica", "calcular_logistica"), ("src.viabilidade", "calcular_viabilidade")]


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def linha_do_resultado(r: ResultadoItem) -> dict:
    """ResultadoItem -> colunas de orcamento_itens (jsonb e datas já serializados)."""
    linha = r.model_dump(mode="json", exclude={"item_id"})
    linha["atualizado_em"] = _agora().isoformat()
    return linha


def item_da_linha(linha: dict) -> ItemEntrada:
    classificacao = linha.get("classificacao")
    return ItemEntrada(
        id=str(linha["id"]), descricao=linha["descricao"],
        quantidade=float(linha["quantidade"]) if linha.get("quantidade") is not None else None,
        unidade=linha.get("unidade"), categoria=linha.get("categoria"),
        classificacao=classificacao if classificacao in ("definido", "pendente_especificacao") else None)


# ------------------------------------------------------------------ acesso ao banco
class Banco(Protocol):
    async def reservar(self, orcamento_id: str) -> bool: ...
    async def itens_para_pesquisar(self, orcamento_id: str) -> list[ItemEntrada]: ...
    async def item(self, item_id: str) -> ItemEntrada | None: ...
    async def gravar_item(self, resultado: ResultadoItem) -> None: ...
    async def marcar_item(self, item_id: str, campos: dict) -> None: ...
    async def concluir(self, orcamento_id: str, erro: str | None = None) -> None: ...


class BancoSupabase:
    """Implementação real (supabase-py é síncrono: cada chamada vai para uma thread)."""

    def __init__(self, cliente=None):
        if cliente is None:
            from .database import get_supabase
            cliente = get_supabase()
        self.sb = cliente

    async def _rodar(self, fn):
        return await asyncio.to_thread(fn)

    async def reservar(self, orcamento_id: str) -> bool:
        """Um único UPDATE condicional (atômico): dois cliques não pesquisam duas vezes."""
        limite = (_agora() - JANELA_TRAVADO).isoformat()
        r = await self._rodar(lambda: self.sb.table(ORCAMENTOS)
                              .update({"status_pesquisa": "pesquisando", "pesquisa_iniciada_em": _agora().isoformat(),
                                       "pesquisa_erro": None})
                              .eq("id", orcamento_id)
                              .or_(f"status_pesquisa.in.(pendente,falhou),"
                                   f"and(status_pesquisa.eq.pesquisando,pesquisa_iniciada_em.lt.{limite})")
                              .execute())
        return bool(r.data)

    async def itens_para_pesquisar(self, orcamento_id: str) -> list[ItemEntrada]:
        r = await self._rodar(lambda: self.sb.table(ITENS).select(",".join(COLUNAS_LIDAS))
                              .eq("orcamento_id", orcamento_id).eq("status", "buscando").execute())
        return [item_da_linha(x) for x in r.data or []]

    async def item(self, item_id: str) -> ItemEntrada | None:
        r = await self._rodar(lambda: self.sb.table(ITENS).select(",".join(COLUNAS_LIDAS))
                              .eq("id", item_id).limit(1).execute())
        return item_da_linha(r.data[0]) if r.data else None

    async def gravar_item(self, resultado: ResultadoItem) -> None:
        linha = linha_do_resultado(resultado)
        await self._rodar(lambda: self.sb.table(ITENS).update(linha).eq("id", resultado.item_id).execute())

    async def marcar_item(self, item_id: str, campos: dict) -> None:
        await self._rodar(lambda: self.sb.table(ITENS).update({**campos, "atualizado_em": _agora().isoformat()})
                          .eq("id", item_id).execute())

    async def concluir(self, orcamento_id: str, erro: str | None = None) -> None:
        await self._rodar(lambda: self.sb.table(ORCAMENTOS).update({
            "status_pesquisa": "falhou" if erro else "concluida", "pesquisa_erro": erro,
            "pesquisa_concluida_em": _agora().isoformat()}).eq("id", orcamento_id).execute())


# ------------------------------------------------------------------ fluxo
async def _chamar_fatia_c(orcamento_id: str) -> list[str]:
    """Chama logística e viabilidade da fatia C se já existirem. Falha da C não derruba a pesquisa."""
    feitos = []
    for modulo, nome in GANCHOS_FIM:
        try:
            fn = getattr(importlib.import_module(modulo), nome)
        except (ImportError, AttributeError):
            logger.info("Fatia C: %s.%s ainda não existe; pulando", modulo, nome)
            continue
        try:
            r = fn(orcamento_id)
            if inspect.isawaitable(r):
                await r
            feitos.append(nome)
        except Exception:  # noqa: BLE001
            logger.exception("Fatia C: %s falhou para o orçamento %s", nome, orcamento_id)
    return feitos


@observe(name="orcamento")
async def _pesquisar_orcamento(orcamento_id: str, banco: Banco, opcoes: dict) -> dict:
    if not await banco.reservar(orcamento_id):
        return {"orcamento_id": orcamento_id, "status": "ja_em_andamento_ou_concluido", "itens": 0}
    try:
        itens = await banco.itens_para_pesquisar(orcamento_id)
        resultados = await pesquisar_itens(itens, ao_terminar=banco.gravar_item, **opcoes)
    except Exception as exc:  # noqa: BLE001 — erro geral (banco fora, etc.): marca falhou e libera novo clique
        logger.exception("Pesquisa do orçamento %s falhou", orcamento_id)
        await banco.concluir(orcamento_id, erro=f"{type(exc).__name__}: {exc}"[:500])
        return {"orcamento_id": orcamento_id, "status": "falhou", "itens": 0}
    await banco.concluir(orcamento_id)
    fatia_c = await _chamar_fatia_c(orcamento_id)
    contagem: dict[str, int] = {}
    for r in resultados:
        contagem[r.status] = contagem.get(r.status, 0) + 1
    return {"orcamento_id": orcamento_id, "status": "concluida", "itens": len(resultados),
            "por_status": contagem, "fatia_c": fatia_c}


async def pesquisar_orcamento(orcamento_id: str, banco: Banco | None = None, **opcoes) -> dict:
    """Ponto de entrada da fatia A. Pesquisa só os itens com status 'buscando' e grava cada um ao ficar pronto.
    Langfuse: 1 árvore por orçamento (session_id = orcamento_id), 1 galho por item."""
    banco = banco or BancoSupabase()
    with propagate_attributes(trace_name="orcamento", session_id=str(orcamento_id), tags=["fatia-b"]):
        return await _pesquisar_orcamento(str(orcamento_id), banco, opcoes)


@observe(name="repesquisar_item")
async def repesquisar_item(item_id: str, nova_descricao: str | None = None, banco: Banco | None = None,
                           **opcoes) -> ResultadoItem | None:
    """Botão "Pesquisar de novo" ou resposta do arquiteto à pergunta (nova_descricao = item especificado).
    Ignora o cache: o objetivo é um preço novo."""
    banco = banco or BancoSupabase()
    item = await banco.item(item_id)
    if item is None:
        return None
    campos = {"status": "buscando", "pergunta": None, "motivo": None}
    if nova_descricao:
        item = item.model_copy(update={"descricao": nova_descricao, "classificacao": "definido"})
        campos |= {"descricao": nova_descricao, "classificacao": "definido"}
    await banco.marcar_item(item_id, campos)   # a tela volta a mostrar "buscando" na hora
    resultado = await pesquisar_item(item, usar_cache=False, **opcoes)
    await banco.gravar_item(resultado)
    return resultado
