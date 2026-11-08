"""Modo gravação de vídeo: o agente "pesquisa" em segundos reproduzindo resultados REAIS já pesquisados.

Para cada item enviado, procura em `orcamento_itens` o resultado mais recente de uma pesquisa de verdade com a MESMA
descrição, quantidade e unidade (preço, fontes com os links das lojas, foto, embalagens, pergunta, consumo) e o grava
no item novo, um por vez, com pausas curtas: a tela recebe tudo pelo Realtime, igual à pesquisa real. Item sem
gravação anterior é pesquisado de verdade (mais lento, mas nunca inventado). No fim roda a Fatia C de verdade
(logística, viabilidade, ganho), então estimativa, Excel, PDF e "Ver o raciocínio da IA" funcionam como no fluxo real.

Nada aqui chama LLM nem busca para os itens reproduzidos. Python puro sobre o banco.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .config import get_settings
from .custo import acumular as acumular_custo
from .modelos import ItemEntrada, ResultadoItem
from .orcamento import ITENS, ORCAMENTOS, BancoSupabase, _chamar_fatia_c, _gravar_e_conferir, _local_da_obra
from .pesquisa import pesquisar_itens
from .regiao import na_obra

logger = logging.getLogger(__name__)

CAMPOS_RESULTADO = [c for c in ResultadoItem.model_fields if c != "item_id"]
STATUS_FINAIS = ("definido", "pendente_especificacao", "nao_encontrado")
PRIMEIRO_ITEM_S = 2.2      # o primeiro preço "chega" depois disso
ENTRE_ITENS_S = 1.5        # e os seguintes, um a um
VARIACAO_S = 0.9
REPESQUISA_S = (3.5, 5.0)  # "Responder" / "Pesquisar de novo"


def _qtd(q: float | None) -> str | None:
    return None if q is None else f"{float(q):g}"


def _ritmo() -> float:
    return max(get_settings().simulacao_ritmo, 0.0)


def buscar_gravacao(sb, descricao: str, quantidade: float | None, unidade: str | None, *,
                    excluir_orcamento: str | None = None, excluir_item: str | None = None) -> dict[str, Any] | None:
    """Resultado mais recente de uma pesquisa real do mesmo item (descrição, quantidade e unidade iguais)."""
    # "*": o banco pode não ter todas as colunas do ResultadoItem (medido em 08/11: falta `validacao`)
    q = sb.table(ITENS).select("*").eq("descricao", descricao.strip()).in_("status", list(STATUS_FINAIS))
    q = q.eq("quantidade", _qtd(quantidade)) if quantidade is not None else q.is_("quantidade", "null")
    q = q.eq("unidade", unidade) if unidade else q.is_("unidade", "null")
    if excluir_orcamento:
        q = q.neq("orcamento_id", excluir_orcamento)
    if excluir_item:
        q = q.neq("id", excluir_item)
    r = q.order("atualizado_em", desc=True).limit(1).execute()
    return dict(r.data[0]) if r.data else None


def resultado_da_gravacao(item_id: str, gravacao: dict[str, Any]) -> ResultadoItem:
    campos = {k: gravacao[k] for k in CAMPOS_RESULTADO if gravacao.get(k) is not None}
    if campos.get("preco_data"):
        # o preço chega "agora", como numa pesquisa nova: a Fatia C conta como reaproveitado o preço anterior ao
        # início da pesquisa, e o ganho dizia "9 de 9 preços reaproveitados" (medido em 08/11)
        campos["preco_data"] = datetime.now(timezone.utc).isoformat()
    return ResultadoItem(item_id=item_id, **campos)


def custos_das_origens(sb, orcamento_ids: set[str]) -> dict[str, float]:
    """Custo de IA por item de cada pesquisa real de origem (custo_usd do orçamento ÷ itens). O banco não guarda o
    custo por item (`pesquisa_detalhes` não existe em orcamento_itens)."""
    if not orcamento_ids:
        return {}
    try:
        r = sb.table(ORCAMENTOS).select("id,custo_usd,qtd_itens").in_("id", sorted(orcamento_ids)).execute()
    except Exception:  # noqa: BLE001
        logger.warning("Não li o custo das pesquisas de origem", exc_info=True)
        return {}
    saida = {}
    for o in r.data or []:
        try:
            saida[str(o["id"])] = float(o.get("custo_usd") or 0) / max(int(o.get("qtd_itens") or 1), 1)
        except (TypeError, ValueError):
            continue
    return saida


def agenda(n: int, ritmo: float, rng: random.Random | None = None) -> list[float]:
    """Instante (s) em que cada item "fica pronto": um a um, com variação, como a pesquisa real."""
    rng = rng or random.Random()
    return [ritmo * (PRIMEIRO_ITEM_S + i * ENTRE_ITENS_S + rng.uniform(0, VARIACAO_S)) for i in range(n)]


async def simular_orcamento(orcamento_id: str, banco: BancoSupabase | None = None) -> dict[str, Any]:
    """Mesmo protocolo de `pesquisar_orcamento` (reserva, grava item a item, conclui, Fatia C), sem pesquisar o que
    já foi pesquisado."""
    banco = banco or BancoSupabase()
    sb = banco.sb
    if not await banco.reservar(orcamento_id):
        return {"orcamento_id": orcamento_id, "status": "ja_em_andamento_ou_concluido", "itens": 0}
    inicio = time.perf_counter()

    async def gravar_no_instante(it: ItemEntrada, g: dict[str, Any], t: float) -> None:
        await asyncio.sleep(max(t - (time.perf_counter() - inicio), 0))
        await banco.gravar_item(resultado_da_gravacao(it.id, g))

    custo_real = 0.0
    try:   # depois da reserva, qualquer falha conclui como "falhou" (nunca fica "pesquisando")
        itens: list[ItemEntrada] = await banco.itens_para_pesquisar(orcamento_id)
        gravacoes = await asyncio.gather(*[
            asyncio.to_thread(buscar_gravacao, sb, it.descricao, it.quantidade, it.unidade,
                              excluir_orcamento=orcamento_id)
            for it in itens])
        reproduzir = [(it, g) for it, g in zip(itens, gravacoes) if g is not None]
        pesquisar = [it for it, g in zip(itens, gravacoes) if g is None]
        instantes = agenda(len(reproduzir), _ritmo())
        random.shuffle(instantes)   # a ordem em que os preços chegam não é a da lista (a real também não é)
        with acumular_custo() as custo:
            tarefas = [gravar_no_instante(it, g, t) for (it, g), t in zip(reproduzir, instantes)]
            if pesquisar:   # sem gravação anterior: pesquisa de verdade, em paralelo
                local, lojas = await _local_da_obra(banco, orcamento_id)

                async def pesquisar_de_verdade() -> None:
                    with na_obra(local, lojas):
                        await pesquisar_itens(pesquisar, ao_terminar=lambda r: _gravar_e_conferir(banco, r))
                tarefas.append(pesquisar_de_verdade())
            await asyncio.gather(*tarefas)
            custo_real = custo.usd
    except Exception as exc:  # noqa: BLE001
        logger.exception("Simulação do orçamento %s falhou", orcamento_id)
        await banco.concluir(orcamento_id, erro=f"{type(exc).__name__}: {exc}"[:500])
        return {"orcamento_id": orcamento_id, "status": "falhou", "itens": 0}

    por_item = await asyncio.to_thread(custos_das_origens, sb, {str(g["orcamento_id"]) for _, g in reproduzir})
    custo_total = sum(por_item.get(str(g["orcamento_id"]), 0.0) for _, g in reproduzir) + custo_real
    await banco.concluir(orcamento_id, custo_usd=custo_total)
    campos: dict[str, Any] = {"tempo_ms": int((time.perf_counter() - inicio) * 1000)}
    origem = Counter(str(g["orcamento_id"]) for _, g in reproduzir).most_common(1)
    if origem:   # "Ver o raciocínio da IA": o trace da pesquisa real que produziu a maior parte dos resultados
        try:
            r = await asyncio.to_thread(lambda: sb.table(ORCAMENTOS).select("trace_url").eq("id", origem[0][0])
                                        .limit(1).execute())
            if r.data and r.data[0].get("trace_url"):
                campos["trace_url"] = r.data[0]["trace_url"]
        except Exception:  # noqa: BLE001
            logger.warning("Não li o trace_url da gravação %s", origem[0][0], exc_info=True)
    await banco.metricas(orcamento_id, campos)
    fatia_c = await _chamar_fatia_c(orcamento_id)
    logger.info("Simulação %s: %d reproduzidos, %d pesquisados de verdade", orcamento_id, len(reproduzir),
                len(pesquisar))
    return {"orcamento_id": orcamento_id, "status": "concluida", "itens": len(itens),
            "reproduzidos": len(reproduzir), "pesquisados": len(pesquisar), "fatia_c": fatia_c}


async def simular_repesquisa(item_id: str, nova_descricao: str | None = None,
                             banco: BancoSupabase | None = None) -> ResultadoItem | None:
    """"Responder" e "Pesquisar de novo" reproduzidos. None = não há gravação: quem chamou pesquisa de verdade."""
    banco = banco or BancoSupabase()
    item = await banco.item(item_id)
    if item is None:
        return None
    descricao = (nova_descricao or item.descricao).strip()
    gravacao = await asyncio.to_thread(buscar_gravacao, banco.sb, descricao, item.quantidade, item.unidade,
                                       excluir_item=item_id)
    if gravacao is None:
        return None
    campos: dict[str, Any] = {"status": "buscando", "pergunta": None, "motivo": None}
    if nova_descricao:
        campos |= {"descricao": descricao, "classificacao": "definido"}
    await banco.marcar_item(item_id, campos)   # a tela mostra "buscando", como na pesquisa real
    await asyncio.sleep(_ritmo() * random.uniform(*REPESQUISA_S))
    resultado = resultado_da_gravacao(item_id, gravacao)
    await banco.gravar_item(resultado)
    if orcamento_id := await banco.orcamento_do_item(item_id):
        por_item = await asyncio.to_thread(custos_das_origens, banco.sb, {str(gravacao.get("orcamento_id"))})
        await banco.somar_custo(orcamento_id, por_item.get(str(gravacao.get("orcamento_id")), 0.0))
        await _chamar_fatia_c(orcamento_id)
    return resultado
