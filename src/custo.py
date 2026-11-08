"""Soma o custo (USD) das chamadas ao LLM de um orçamento, para o "ganho na tela" da Fatia C.

Um `Acumulador` fica num ContextVar: tarefas do asyncio e `asyncio.to_thread` herdam o contexto,
então todas as chamadas do orçamento somam no mesmo objeto sem passar parâmetro por todo o código.
Fora de um orçamento (testes, scripts) `registrar` não faz nada.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import RLock
import math


@dataclass
class Acumulador:
    usd: float = 0.0
    entrada: int = 0
    saida: int = 0
    chamadas: int = 0
    sem_usage: int = 0
    sem_custo: int = 0
    reservado: int = 0
    limite_chamadas: int = 0
    limite_tokens: int = 0
    limite_usd: float = 0
    limite_atingido: bool = False
    paginas: int = 0
    urls: set[str] = field(default_factory=set)
    urls_indisponiveis: set[str] = field(default_factory=set)
    compras_lidas: dict[str, tuple[str, float]] = field(default_factory=dict)

    def resumo(self) -> dict:
        return {"tokens_entrada": self.entrada, "tokens_saida": self.saida,
                "chamadas": self.chamadas, "custo_usd": round(self.usd, 6),
                "consumo_incompleto": bool(self.sem_usage or self.sem_custo),
                "chamadas_sem_usage": self.sem_usage, "limite_atingido": self.limite_atingido,
                "paginas_lidas": self.paginas}


_pilha: ContextVar[tuple[Acumulador, ...]] = ContextVar("consumo", default=())
_lock = RLock()


class LimitePesquisa(RuntimeError):
    pass


@contextmanager
def acumular(acc=None, *, item=False):
    """Dentro do bloco, `registrar()` soma neste acumulador."""
    from .config import get_settings
    s = get_settings()
    acc = acc or Acumulador(
        limite_chamadas=s.pesquisa_max_chamadas_item if item else s.pesquisa_max_chamadas_execucao,
        limite_tokens=s.pesquisa_max_tokens_item if item else s.pesquisa_max_tokens_execucao,
        limite_usd=s.pesquisa_limite_usd_item if item else s.pesquisa_limite_usd_execucao)
    token = _pilha.set((*_pilha.get(), acc))
    try:
        yield acc
    finally:
        _pilha.reset(token)


def atual():
    return _pilha.get()[-1] if _pilha.get() else None


def reservar(mensagens, saida: int):
    """Reserva bytes UTF-8 + saída antes do envio. Falha mantém consumo desconhecido."""
    import json
    n = len(json.dumps(mensagens, ensure_ascii=False).encode("utf-8")) + saida
    accs = _pilha.get()
    with _lock:
        for a in accs:
            if ((a.limite_chamadas and a.chamadas >= a.limite_chamadas)
                or (a.limite_tokens and a.entrada + a.saida + a.reservado + n > a.limite_tokens)
                or (a.limite_usd and a.usd >= a.limite_usd)):
                for ativo in accs:
                    ativo.limite_atingido = True
                raise LimitePesquisa("limite de consumo da pesquisa atingido")
        for a in accs:
            a.chamadas += 1
            a.sem_usage += 1
            a.reservado += n
    return accs, n


def registrar_resposta(reserva, usage):
    accs, n = reserva
    if usage is None:
        return
    valor = getattr(usage, "cost", None)
    try:
        valor = float(valor)
        if not math.isfinite(valor) or valor < 0:
            valor = None
    except (ValueError, TypeError):
        valor = None
    with _lock:
        for a in accs:
            a.sem_usage -= 1
            a.reservado -= n
            a.entrada += max(0, getattr(usage, "prompt_tokens", 0) or 0)
            a.saida += max(0, getattr(usage, "completion_tokens", 0) or 0)
            if valor is None:
                a.sem_custo += 1
            else:
                a.usd += valor


def registrar(usd) -> None:
    try:
        valor = float(usd or 0)
    except (TypeError, ValueError):
        return
    if math.isfinite(valor) and valor >= 0:
        with _lock:
            for acc in _pilha.get():
                acc.usd += valor


def registrar_paginas(quantidade: int):
    with _lock:
        for acc in _pilha.get():
            acc.paginas += quantidade
