"""Soma o custo (USD) das chamadas ao LLM de um orçamento, para o "ganho na tela" da Fatia C.

Um `Acumulador` fica num ContextVar: tarefas do asyncio e `asyncio.to_thread` herdam o contexto,
então todas as chamadas do orçamento somam no mesmo objeto sem passar parâmetro por todo o código.
Fora de um orçamento (testes, scripts) `registrar` não faz nada.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class Acumulador:
    usd: float = 0.0


_atual: ContextVar[Acumulador | None] = ContextVar("custo_orcamento", default=None)


@contextmanager
def acumular():
    """Dentro do bloco, `registrar()` soma neste acumulador."""
    acc = Acumulador()
    token = _atual.set(acc)
    try:
        yield acc
    finally:
        _atual.reset(token)


def registrar(usd) -> None:
    acc = _atual.get()
    if acc is not None:
        try:
            acc.usd += float(usd or 0)
        except (TypeError, ValueError):
            pass
