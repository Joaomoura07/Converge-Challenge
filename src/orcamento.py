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
import re
from datetime import datetime, timedelta, timezone
from typing import Protocol

from langfuse import observe, propagate_attributes

from .custo import acumular as acumular_custo
from .modelos import ItemEntrada, ResultadoItem
from .pesquisa import pesquisar_item, pesquisar_itens

logger = logging.getLogger(__name__)

ORCAMENTOS, ITENS = "orcamentos", "orcamento_itens"
COLUNAS_LIDAS = ["id", "orcamento_id", "descricao", "quantidade", "unidade", "categoria", "classificacao", "status"]
COLUNAS_GRAVADAS = [c for c in ResultadoItem.model_fields if c != "item_id"] + ["atualizado_em"]
JANELA_TRAVADO = timedelta(minutes=3)   # execução morta pela Vercel no meio libera o orçamento depois disso
# Gancho da fatia C, chamado no fim: (módulo, função). Uma chamada só faz frete + viabilidade + ganho e grava em
# `orcamentos`. Ausente (branch da C ainda não juntada) = só registra no log.
GANCHOS_FIM = [("src.rotas_resultado", "resultado")]


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def linha_do_resultado(r: ResultadoItem) -> dict:
    """ResultadoItem -> colunas de orcamento_itens (jsonb e datas já serializados)."""
    linha = r.model_dump(mode="json", exclude={"item_id"})
    linha["atualizado_em"] = _agora().isoformat()
    return linha


def _coluna_ausente(exc: Exception) -> str | None:
    """PostgREST PGRST204: "Could not find the 'premissa' column of 'orcamento_itens' in the schema cache"."""
    m = re.search(r"Could not find the '([^']+)' column", str(exc))
    return m.group(1) if m and "PGRST204" in str(exc) else None


# Classificação como o SQL da fatia A grava (itens_classificacao_ck aceita 'definido' e 'pendente', medido em 07/11)
# -> como a fatia B usa. Sem isso, item genérico vindo do site era pesquisado como definido e sem pergunta.
CLASSIFICACAO_DA_A = {"definido": "definido", "pendente": "pendente_especificacao",
                      "pendente_especificacao": "pendente_especificacao"}


def item_da_linha(linha: dict) -> ItemEntrada:
    classificacao = CLASSIFICACAO_DA_A.get((linha.get("classificacao") or "").strip().lower())
    return ItemEntrada(
        id=str(linha["id"]), descricao=linha["descricao"],
        quantidade=float(linha["quantidade"]) if linha.get("quantidade") is not None else None,
        unidade=linha.get("unidade"), categoria=linha.get("categoria"),
        classificacao=classificacao)


# ------------------------------------------------------------------ acesso ao banco
class Banco(Protocol):
    async def reservar(self, orcamento_id: str) -> bool: ...
    async def itens_para_pesquisar(self, orcamento_id: str) -> list[ItemEntrada]: ...
    async def item(self, item_id: str) -> ItemEntrada | None: ...
    async def gravar_item(self, resultado: ResultadoItem) -> None: ...
    async def marcar_item(self, item_id: str, campos: dict) -> None: ...
    async def concluir(self, orcamento_id: str, erro: str | None = None, custo_usd: float | None = None) -> None: ...
    async def orcamento_do_item(self, item_id: str) -> str | None: ...
    async def somar_custo(self, orcamento_id: str, usd: float) -> None: ...


class BancoSupabase:
    """Implementação real (supabase-py é síncrono: cada chamada vai para uma thread)."""

    def __init__(self, cliente=None):
        if cliente is None:
            from .database import get_supabase
            cliente = get_supabase()
        self.sb = cliente
        self.colunas_ausentes: set[str] = set()

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
        return bool(r.data)   # o tempo do "ganho" a Fatia C lê de pesquisa_iniciada_em / pesquisa_concluida_em

    async def _extras(self, orcamento_id: str, campos: dict) -> None:
        """Grava colunas da Fatia C em `orcamentos` sem nunca derrubar a pesquisa."""
        try:
            await self._rodar(lambda: self.sb.table(ORCAMENTOS).update(campos).eq("id", orcamento_id).execute())
        except Exception:  # noqa: BLE001
            logger.warning("Não gravei %s em orcamentos (coluna existe?)", sorted(campos), exc_info=True)

    async def orcamento_do_item(self, item_id: str) -> str | None:
        r = await self._rodar(lambda: self.sb.table(ITENS).select("orcamento_id").eq("id", item_id).limit(1).execute())
        return str(r.data[0]["orcamento_id"]) if r.data else None

    async def somar_custo(self, orcamento_id: str, usd: float) -> None:
        """Soma o custo de uma nova pesquisa (ex.: 'Pesquisar de novo') ao total do orçamento."""
        if not usd:
            return
        try:
            r = await self._rodar(lambda: self.sb.table(ORCAMENTOS).select("custo_usd").eq("id", orcamento_id)
                                  .limit(1).execute())
            atual = float((r.data[0].get("custo_usd") if r.data else 0) or 0)
        except Exception:  # noqa: BLE001
            logger.warning("Não li custo_usd do orçamento %s", orcamento_id, exc_info=True)
            return
        await self._extras(orcamento_id, {"custo_usd": round(atual + usd, 6)})

    async def itens_para_pesquisar(self, orcamento_id: str) -> list[ItemEntrada]:
        r = await self._rodar(lambda: self.sb.table(ITENS).select(",".join(COLUNAS_LIDAS))
                              .eq("orcamento_id", orcamento_id).eq("status", "buscando").execute())
        return [item_da_linha(x) for x in r.data or []]

    async def item(self, item_id: str) -> ItemEntrada | None:
        r = await self._rodar(lambda: self.sb.table(ITENS).select(",".join(COLUNAS_LIDAS))
                              .eq("id", item_id).limit(1).execute())
        return item_da_linha(r.data[0]) if r.data else None

    async def gravar_item(self, resultado: ResultadoItem) -> None:
        """Coluna que o SQL da fatia A ainda não tem (medido em 07/11: `premissa`) sai da linha, com aviso,
        em vez de derrubar a gravação inteira: senão o item ficaria "buscando" para sempre na tela."""
        linha = {k: v for k, v in linha_do_resultado(resultado).items() if k not in self.colunas_ausentes}
        for _ in range(len(linha)):
            try:
                await self._rodar(lambda: self.sb.table(ITENS).update(linha).eq("id", resultado.item_id).execute())
                return
            except Exception as exc:  # noqa: BLE001
                coluna = _coluna_ausente(exc)
                if coluna is None or coluna not in linha:
                    raise
                logger.warning("orcamento_itens não tem a coluna '%s' (avise a fatia A): gravando sem ela", coluna)
                self.colunas_ausentes.add(coluna)
                linha = {k: v for k, v in linha.items() if k != coluna}

    async def marcar_item(self, item_id: str, campos: dict) -> None:
        await self._rodar(lambda: self.sb.table(ITENS).update({**campos, "atualizado_em": _agora().isoformat()})
                          .eq("id", item_id).execute())

    async def concluir(self, orcamento_id: str, erro: str | None = None, custo_usd: float | None = None) -> None:
        await self._rodar(lambda: self.sb.table(ORCAMENTOS).update({
            "status_pesquisa": "falhou" if erro else "concluida", "pesquisa_erro": erro,
            "pesquisa_concluida_em": _agora().isoformat()}).eq("id", orcamento_id).execute())
        if custo_usd is not None:
            await self._extras(orcamento_id, {"custo_usd": round(custo_usd, 6)})


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
            if inspect.iscoroutinefunction(fn):
                await fn(orcamento_id)
            else:   # função síncrona (consulta de CEP, banco): numa thread para não travar o event loop
                r = await asyncio.to_thread(fn, orcamento_id)
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
    with acumular_custo() as custo:
        try:
            itens = await banco.itens_para_pesquisar(orcamento_id)
            resultados = await pesquisar_itens(itens, ao_terminar=banco.gravar_item, **opcoes)
        except Exception as exc:  # noqa: BLE001 — erro geral (banco fora, etc.): marca falhou e libera novo clique
            logger.exception("Pesquisa do orçamento %s falhou", orcamento_id)
            await banco.concluir(orcamento_id, erro=f"{type(exc).__name__}: {exc}"[:500], custo_usd=custo.usd)
            return {"orcamento_id": orcamento_id, "status": "falhou", "itens": 0}
    await banco.concluir(orcamento_id, custo_usd=custo.usd)   # antes da C: o "ganho" lê custo_usd
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
    with acumular_custo() as custo:
        resultado = await pesquisar_item(item, usar_cache=False, **opcoes)
    await banco.gravar_item(resultado)
    # Preço novo: soma o custo ao orçamento e recalcula frete/viabilidade/ganho (idempotente).
    orcamento_id = await banco.orcamento_do_item(item_id)
    if orcamento_id:
        await banco.somar_custo(orcamento_id, custo.usd)
        await _chamar_fatia_c(orcamento_id)
    return resultado
