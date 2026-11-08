"""Uma porta só para o serper.dev (Google Shopping, Maps e busca), com limite de chamadas simultâneas.

Medido em 08/11: 14 itens em paralelo (Shopping + 2 buscas regionais por item + Maps) passaram do limite por minuto
e o Serper devolveu 429; itens ficaram sem nenhum preço. Aqui: no máximo SIMULTANEAS chamadas ao mesmo tempo,
rodízio de chaves e, no 429, uma espera curta e nova tentativa. Nunca levanta: falha = None.
"""

from __future__ import annotations

import asyncio
import logging
import random
import weakref

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)

SIMULTANEAS = 4
TENTATIVAS_429 = 3
_semaforos: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# Chaves que responderam "Not enough credits": vão para o fim da fila (medido em 08/11: a 1ª chave com saldo -27
# devolvia HTTP 400 e a função desistia sem tentar as outras duas, que tinham ~2.500 créditos cada; Shopping, Maps
# e fotos de reserva ficavam vazios).
_sem_credito: set[str] = set()


def _sem_credito_na_resposta(r: httpx.Response) -> bool:
    if r.status_code == 402:
        return True
    if r.status_code != 400:
        return False
    try:
        return "credit" in r.text.lower()
    except Exception:  # noqa: BLE001
        return False


def _porteiro() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _semaforos:
        _semaforos[loop] = asyncio.Semaphore(SIMULTANEAS)
    return _semaforos[loop]


async def post(cli: httpx.AsyncClient, url: str, corpo: dict, chaves: list[str] | None = None) -> dict | None:
    """JSON da resposta (HTTP 200) ou None. Tenta cada chave; 429 espera e tenta de novo."""
    chaves = get_settings().serper_keys if chaves is None else chaves
    chaves = [k for k in chaves if k not in _sem_credito] + [k for k in chaves if k in _sem_credito]
    for tentativa in range(TENTATIVAS_429):
        limite = False
        for k in chaves:
            try:
                async with _porteiro():
                    r = await cli.post(url, headers={"X-API-KEY": k, "Content-Type": "application/json"}, json=corpo)
            except Exception as exc:  # noqa: BLE001 — rede, timeout
                logger.warning("Serper falhou (%s)", type(exc).__name__)
                return None
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:  # noqa: BLE001
                    return None
            if r.status_code == 429:
                limite = True
                continue
            if r.status_code in (401, 403):
                continue   # chave inválida ou sem crédito: próxima
            if _sem_credito_na_resposta(r):
                _sem_credito.add(k)
                continue   # "Not enough credits" (HTTP 400): próxima chave
            logger.warning("Serper respondeu HTTP %s", r.status_code)
            return None
        if not limite:
            return None
        await asyncio.sleep(1.0 + tentativa + random.random())
    logger.warning("Serper: limite por minuto (429) em todas as tentativas")
    return None
