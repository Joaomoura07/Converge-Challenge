"""Rodízio das chaves da Featherless (FEATHERLESS_API_KEYS).

Cada chave tem a PRÓPRIA cota de chamadas simultâneas na Featherless (skills/02-featherless-integration.md, seção 3).
Com várias chaves do time, a pesquisa pode fazer mais chamadas ao mesmo tempo sem sobrecarregar nenhuma conta:

- extração: `pesquisa_concorrencia_llm` vagas POR CHAVE; cada chamada pega a chave com vaga livre e menos ocupada;
- agente (GLM-5.2): com 2+ chaves, a ÚLTIMA fica só para ele (extração e agente não disputam a mesma cota);
- chave que falha (resposta vazia, 429, 5xx) "esfria" por alguns segundos e a nova tentativa vai para outra chave.
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from contextlib import asynccontextmanager

from .config import get_settings

logger = logging.getLogger(__name__)

ESFRIAR_S = 30
_esfria_ate: dict[str, float] = {}   # global (não depende do event loop): o problema é da conta, não da requisição


def chaves_extracao() -> list[str]:
    chaves = get_settings().featherless_keys
    return chaves[:-1] if len(chaves) >= 2 else chaves


def chave_agente() -> str:
    chaves = get_settings().featherless_keys
    return chaves[-1] if chaves else ""


def esfriar(chave: str, segundos: float = ESFRIAR_S) -> None:
    _esfria_ate[chave] = time.monotonic() + segundos
    logger.info("Featherless: chave %d esfriando por %.0f s", _numero(chave), segundos)


def _quente(chave: str) -> bool:
    return _esfria_ate.get(chave, 0) <= time.monotonic()


def _numero(chave: str) -> int:
    chaves = get_settings().featherless_keys
    return chaves.index(chave) + 1 if chave in chaves else 0   # só o número aparece no log, nunca a chave


class PoolChaves:
    """Vagas por chave dentro de UM event loop (as primitivas do asyncio pertencem ao loop)."""

    def __init__(self, chaves: list[str], vagas_por_chave: int):
        self.chaves = list(chaves) or [""]
        self.vagas = max(1, vagas_por_chave)
        self.em_uso = {c: 0 for c in self.chaves}
        self._cond = asyncio.Condition()

    def _escolher(self, evitar: str | None) -> str | None:
        livres = [c for c in self.chaves if self.em_uso[c] < self.vagas]
        if not livres:
            return None
        # quente e diferente da que acabou de falhar > só diferente > qualquer livre; depois a menos ocupada
        return min(livres, key=lambda c: (not _quente(c), c == evitar, self.em_uso[c]))

    @asynccontextmanager
    async def vaga(self, evitar: str | None = None):
        async with self._cond:
            while (chave := self._escolher(evitar)) is None:
                await self._cond.wait()
            self.em_uso[chave] += 1
        try:
            yield chave
        finally:
            async with self._cond:
                self.em_uso[chave] -= 1
                self._cond.notify()


_pools: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def pool_extracao() -> PoolChaves:
    """Um pool por event loop, guardado pelo próprio loop (mesmo cuidado de `precos.semaforo_do_loop`)."""
    loop = asyncio.get_running_loop()
    chaves = chaves_extracao()
    pool = _pools.get(loop)
    if pool is None or pool.chaves != (chaves or [""]):
        pool = _pools[loop] = PoolChaves(chaves, get_settings().pesquisa_concorrencia_llm)
    return pool
