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
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Protocol

from langfuse import observe, propagate_attributes

from .alternativas import Objetivo, decidir, sugerir_alternativa
from .regiao import na_obra, preparar_obra
from .custo import acumular as acumular_custo
from .modelos import ItemEntrada, ResultadoItem
from .pesquisa import aceitar_media_estimada, aceitar_mais_proximo, pesquisar_item, pesquisar_itens
from .validacao_serper import validar as validar_preco

logger = logging.getLogger(__name__)

ORCAMENTOS, ITENS = "orcamentos", "orcamento_itens"
COLUNAS_LIDAS = ["id", "orcamento_id", "descricao", "quantidade", "unidade", "categoria", "classificacao", "status"]
COLUNAS_GRAVADAS = [c for c in ResultadoItem.model_fields if c != "item_id"] + ["atualizado_em"]
# Execução morta pela Vercel no meio libera o orçamento depois disso. PRECISA ser maior que o tempo máximo da função
# (300 s na Vercel): com 3 min, uma pesquisa viva de 200 s podia ser "reassumida" por outro clique e as duas gravariam.
TEMPO_MAXIMO_FUNCAO = timedelta(seconds=300)
JANELA_TRAVADO = timedelta(minutes=6)
TENTATIVAS_GRAVAR = 2   # novas tentativas de gravar um item depois de uma falha passageira do banco
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

    async def cep(self, orcamento_id: str) -> str | None:
        """CEP da obra (a fatia A grava só dígitos em orcamentos.cep)."""
        r = await self._rodar(lambda: self.sb.table(ORCAMENTOS).select("cep").eq("id", orcamento_id).limit(1).execute())
        return (r.data[0].get("cep") if r.data else None) or None

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

    async def resultado_atual(self, item_id: str) -> ResultadoItem | None:
        """O que o item mostra hoje (para devolver se a alternativa não se sustentar). Linha que não forma um
        ResultadoItem válido (ex.: ainda "buscando") = None."""
        colunas = ["id"] + [c for c in COLUNAS_GRAVADAS if c != "atualizado_em" and c not in self.colunas_ausentes]
        try:
            r = await self._rodar(lambda: self.sb.table(ITENS).select(",".join(colunas)).eq("id", item_id)
                                  .limit(1).execute())
            if not r.data:
                return None
            linha = dict(r.data[0])
            if linha.get("status") == "buscando":   # pesquisa em andamento ou morta: não há o que devolver
                return None
            return ResultadoItem(item_id=str(linha.pop("id")), **{k: v for k, v in linha.items() if v is not None})
        except Exception:  # noqa: BLE001
            logger.warning("Não li o resultado atual do item %s", item_id, exc_info=True)
            return None

    async def gravar_item(self, resultado: ResultadoItem) -> None:
        """Coluna que o SQL da fatia A ainda não tem (medido em 07/11: `premissa`) sai da linha, com aviso,
        em vez de derrubar a gravação inteira: senão o item ficaria "buscando" para sempre na tela."""
        linha = {k: v for k, v in linha_do_resultado(resultado).items() if k not in self.colunas_ausentes}
        falhas = 0
        for _ in range(len(linha) + TENTATIVAS_GRAVAR):
            try:
                await self._rodar(lambda: self.sb.table(ITENS).update(linha).eq("id", resultado.item_id).execute())
                return
            except Exception as exc:  # noqa: BLE001
                coluna = _coluna_ausente(exc)
                if coluna is None or coluna not in linha:
                    # Falha passageira: medido no site em 07/11, 4 de 53 itens gravados ao mesmo tempo falharam e
                    # gravaram normalmente na nova tentativa. Antes, o item ficava "buscando" para sempre.
                    falhas += 1
                    if falhas > TENTATIVAS_GRAVAR:
                        raise
                    logger.warning("Gravação do item %s falhou (%s): tentando de novo", resultado.item_id,
                                   type(exc).__name__)
                    await asyncio.sleep(0.4 * falhas + random.random() / 2)
                    continue
                logger.warning("orcamento_itens não tem a coluna '%s' (avise a fatia A): gravando sem ela", coluna)
                self.colunas_ausentes.add(coluna)
                linha = {k: v for k, v in linha.items() if k != coluna}

    async def marcar_item(self, item_id: str, campos: dict) -> None:
        await self._rodar(lambda: self.sb.table(ITENS).update({**campos, "atualizado_em": _agora().isoformat()})
                          .eq("id", item_id).execute())

    async def metricas(self, orcamento_id: str, campos: dict) -> None:
        """trace_url e tempo_ms (colunas do SQL único que ninguém gravava). Nunca derruba a pesquisa."""
        await self._extras(orcamento_id, campos)

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


def _link_do_trace() -> str | None:
    """Link do trace atual, público (o jurado abre sem login). Telemetria nunca derruba a pesquisa."""
    try:
        from langfuse import get_client
        lf = get_client()
        trace_id = lf.get_current_trace_id()
        if not trace_id:
            return None
        lf.set_current_trace_as_public()
        return lf.get_trace_url(trace_id=trace_id)
    except Exception:  # noqa: BLE001
        logger.warning("Langfuse indisponível: orçamento sem trace_url", exc_info=True)
        return None


async def _gravar_metricas(banco: Banco, orcamento_id: str, inicio: float) -> None:
    if not hasattr(banco, "metricas"):
        return
    campos = {"tempo_ms": int((time.perf_counter() - inicio) * 1000)}
    if url := _link_do_trace():
        campos["trace_url"] = url
    await banco.metricas(orcamento_id, campos)


async def _gravar_e_conferir(banco: Banco, r: ResultadoItem) -> None:
    """Grava o item (a tela já o mostra) e, se houver chave do Serper, confere o preço numa 2ª fonte e regrava só
    se isso trouxe algo. Falha da conferência nunca desfaz nem atrasa a gravação do item."""
    await banco.gravar_item(r)
    try:
        conferido = await validar_preco(r)
        if conferido.validacao is not None and conferido is not r:
            await banco.gravar_item(conferido)
    except Exception:  # noqa: BLE001
        logger.warning("Conferência de preço do item %s falhou", r.item_id, exc_info=True)


@observe(name="orcamento")
async def _pesquisar_orcamento(orcamento_id: str, banco: Banco, opcoes: dict) -> dict:
    if not await banco.reservar(orcamento_id):
        return {"orcamento_id": orcamento_id, "status": "ja_em_andamento_ou_concluido", "itens": 0}
    inicio = time.perf_counter()
    with acumular_custo() as custo:
        try:
            itens = await banco.itens_para_pesquisar(orcamento_id)
            resultados = await pesquisar_itens(itens, ao_terminar=lambda r: _gravar_e_conferir(banco, r), **opcoes)
        except Exception as exc:  # noqa: BLE001 — erro geral (banco fora, etc.): marca falhou e libera novo clique
            logger.exception("Pesquisa do orçamento %s falhou", orcamento_id)
            await banco.concluir(orcamento_id, erro=f"{type(exc).__name__}: {exc}"[:500], custo_usd=custo.usd)
            return {"orcamento_id": orcamento_id, "status": "falhou", "itens": 0}
    await banco.concluir(orcamento_id, custo_usd=custo.usd)   # antes da C: o "ganho" lê custo_usd
    await _gravar_metricas(banco, orcamento_id, inicio)
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
    local, lojas = await _local_da_obra(banco, str(orcamento_id))
    with propagate_attributes(trace_name="orcamento", session_id=str(orcamento_id), tags=["fatia-b"]),             na_obra(local, lojas):
        return await _pesquisar_orcamento(str(orcamento_id), banco, opcoes)


async def _local_da_obra(banco: Banco, orcamento_id: str | None):
    """CEP do orçamento → (cidade/UF, lojas da região pelo Google Maps). Qualquer falha = busca sem região."""
    if not orcamento_id or not hasattr(banco, "cep"):
        return None, []
    try:
        return await preparar_obra(await banco.cep(orcamento_id))
    except Exception:  # noqa: BLE001
        logger.warning("Não deu para ler o CEP do orçamento %s: busca sem cidade", orcamento_id)
        return None, []


async def _resultado_atual(banco: Banco, item_id: str) -> ResultadoItem | None:
    if not hasattr(banco, "resultado_atual"):
        return None
    try:
        return await banco.resultado_atual(item_id)
    except Exception:  # noqa: BLE001
        return None


@observe(name="repesquisar_item")
async def repesquisar_item(item_id: str, nova_descricao: str | None = None, banco: Banco | None = None,
                           objetivo: Objetivo | None = None, aceitar_media: bool = False,
                           voltar_para: str | None = None, troca: dict | None = None,
                           **opcoes) -> ResultadoItem | None:
    """Botão "Pesquisar de novo" ou resposta do arquiteto à pergunta (nova_descricao = item especificado).
    Com `aceitar_media` ("Usar a média mesmo assim"), o arquiteto dispensa a especificação: pesquisa o item como está
    (usando o cache, que já guarda a média dos parecidos) e, se houver preço, ele deixa de ser pendente.
    Com `objetivo` (qualidade | preco | semelhante), pesquisa uma ALTERNATIVA sugerida pelo LLM e só troca se ela
    for achada à venda (e, no "preco", sair mais barata); senão o item volta ao que era, com o motivo.
    Quando a alternativa vale, a DESCRIÇÃO do item passa a ser o produto sugerido (pedido de 08/11: senão o próximo
    "Pesquisar de novo" voltava a pesquisar o original); `troca` (dict) recebe o que havia antes e
    `voltar_para` restaura o anterior pelo cache, sem pesquisa nova.
    Ignora o cache: o objetivo é um preço novo. Levanta AlternativaIndisponivel se o LLM não sugerir nada
    (o item fica intocado)."""
    banco = banco or BancoSupabase()
    item = await banco.item(item_id)
    if item is None:
        return None
    orcamento_id = await banco.orcamento_do_item(item_id)
    # Mesma sessão do orçamento no Langfuse: "Pesquisar de novo"/"Responder" aparecem junto da pesquisa original.
    with propagate_attributes(session_id=str(orcamento_id or item_id), tags=["fatia-b", "repesquisar"]):
        return await _repesquisar(item, item_id, orcamento_id, nova_descricao, banco, objetivo, opcoes, aceitar_media,
                                  voltar_para, troca)


def _classificacao(descricao: str) -> tuple[str, str]:
    """(como a fatia A grava no banco, como a B usa): a classificação é da A (classificar_item)."""
    from .revisao import classificar_item
    da_a = classificar_item(descricao)
    return da_a, CLASSIFICACAO_DA_A.get(da_a, "definido")


async def _repesquisar(item: ItemEntrada, item_id: str, orcamento_id: str | None, nova_descricao: str | None,
                       banco: Banco, objetivo: Objetivo | None, opcoes: dict,
                       aceitar_media: bool = False, voltar_para: str | None = None,
                       troca: dict | None = None) -> ResultadoItem:
    with acumular_custo() as custo:
        anterior = alt = None
        busca = item
        if objetivo:
            anterior = await _resultado_atual(banco, item_id)
            atual = (anterior.produto_normalizado if anterior and anterior.produto_normalizado else item.descricao)
            # Antes de marcar "buscando": se o LLM falhar, nada muda na tela.
            ref = ({"preco_atual": anterior.preco_emb_med, "embalagem": anterior.embalagem}
                   if anterior is not None and anterior.preco_emb_med else {})
            alt = await asyncio.to_thread(sugerir_alternativa, atual, objetivo, categoria=item.categoria, **ref)
            busca = item.model_copy(update={"descricao": alt.produto, "classificacao": "definido"})
        campos = {"status": "buscando", "pergunta": None, "motivo": None}
        if nova_descricao:
            item = busca = item.model_copy(update={"descricao": nova_descricao, "classificacao": "definido"})
            campos |= {"descricao": nova_descricao, "classificacao": "definido"}
        if voltar_para:
            # "Voltar para o anterior": o produto de antes volta a ser o título; o preço sai do cache (sem busca nova)
            no_banco, na_b = _classificacao(voltar_para)
            item = busca = item.model_copy(update={"descricao": voltar_para, "classificacao": na_b})
            campos |= {"descricao": voltar_para, "classificacao": no_banco}
        await banco.marcar_item(item_id, campos)   # a tela volta a mostrar "buscando" na hora
        with na_obra(*(await _local_da_obra(banco, orcamento_id))):
            # "Usar a média" quer a média que já foi pesquisada (rápida e sem custo); os demais pedem preço novo.
            resultado = await pesquisar_item(busca, usar_cache=aceitar_media or bool(voltar_para), **opcoes)
        if nova_descricao:
            resultado = aceitar_mais_proximo(resultado)   # respondeu: não repetir a pergunta
        elif aceitar_media:
            resultado = aceitar_media_estimada(resultado)   # dispensou a especificação: fica como estimativa
        if alt is not None:
            resultado, trocou = decidir(resultado, anterior, alt, objetivo, item.descricao)
            escolhida = alt if trocou else None
            if not trocou and anterior is not None:
                # saiu fora da faixa ou repetiu: UMA nova sugestão, dizendo o que evitar
                try:
                    alt2 = await asyncio.to_thread(sugerir_alternativa, atual, objetivo, categoria=item.categoria,
                                                   evitar=(alt.produto,), **ref)
                    busca2 = item.model_copy(update={"descricao": alt2.produto, "classificacao": "definido"})
                    with na_obra(*(await _local_da_obra(banco, orcamento_id))):
                        nova2 = await pesquisar_item(busca2, usar_cache=False, **opcoes)
                    resultado2, trocou2 = decidir(nova2, anterior, alt2, objetivo, item.descricao)
                    if trocou2:
                        resultado, escolhida = resultado2, alt2
                except Exception as exc:  # noqa: BLE001 — a 2ª tentativa nunca piora: fica o anterior com o motivo
                    logger.info("Segunda alternativa indisponível (%s)", type(exc).__name__)
            if escolhida is not None:
                # o título vira o produto sugerido: o próximo "Pesquisar de novo" parte dele, não do original
                await banco.marcar_item(item_id, {"descricao": escolhida.produto, "classificacao": "definido"})
            if troca is not None:
                troca.update({
                    "objetivo": objetivo, "trocou": escolhida is not None,
                    "agora": escolhida.produto if escolhida is not None else None,
                    "antes": {"descricao": atual, "embalagem": anterior.embalagem if anterior else None,
                              "preco_emb_med": anterior.preco_emb_med if anterior else None,
                              "preco_un_med": anterior.preco_un_med if anterior else None,
                              "unidade_preco": anterior.unidade_preco if anterior else None},
                })
    await _gravar_e_conferir(banco, resultado)
    # Preço novo: soma o custo ao orçamento e recalcula frete/viabilidade/ganho (idempotente).
    if orcamento_id:
        await banco.somar_custo(orcamento_id, custo.usd)
        await _chamar_fatia_c(orcamento_id)
    return resultado
