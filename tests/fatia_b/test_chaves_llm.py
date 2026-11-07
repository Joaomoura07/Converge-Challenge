"""Rodízio das chaves da Featherless: vagas por chave, chave do agente separada e chave que falha esfria."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import APIStatusError

import src.chaves_llm as ch
import src.precos as p


@pytest.fixture
def tres_chaves(monkeypatch):
    s = NS(featherless_keys=["fw-1", "fw-2", "fw-3"], pesquisa_concorrencia_llm=2)
    monkeypatch.setattr(ch, "get_settings", lambda: s)
    monkeypatch.setattr(ch, "_esfria_ate", {})
    return s


def test_ultima_chave_fica_so_para_o_agente(tres_chaves):
    assert ch.chaves_extracao() == ["fw-1", "fw-2"] and ch.chave_agente() == "fw-3"


@pytest.mark.parametrize("chaves,extracao,agente", [(["fw-1"], ["fw-1"], "fw-1"), ([], [], "")])
def test_com_uma_chave_extracao_e_agente_dividem(monkeypatch, chaves, extracao, agente):
    monkeypatch.setattr(ch, "get_settings", lambda: NS(featherless_keys=chaves))
    assert ch.chaves_extracao() == extracao and ch.chave_agente() == agente


def test_cada_chave_tem_a_propria_cota_e_reparte_a_carga(tres_chaves):
    async def cenario():
        pool = ch.PoolChaves(ch.chaves_extracao(), 2)
        usadas, abertas = [], []
        for _ in range(4):                         # 2 chaves × 2 vagas
            cm = pool.vaga()
            usadas.append(await cm.__aenter__())
            abertas.append(cm)
        quinta = asyncio.create_task(pool.vaga().__aenter__())
        await asyncio.sleep(0.05)
        assert not quinta.done(), "sem vaga em nenhuma chave: a 5ª espera"
        await abertas[0].__aexit__(None, None, None)
        assert await asyncio.wait_for(quinta, 1) == usadas[0], "pega a vaga que liberou"
        return usadas

    usadas = asyncio.run(cenario())
    assert sorted(usadas) == ["fw-1", "fw-1", "fw-2", "fw-2"], "reparte entre as chaves em vez de lotar a primeira"


def test_chave_que_falhou_esfria_e_a_proxima_vai_para_outra(tres_chaves):
    async def cenario():
        pool = ch.PoolChaves(["fw-1", "fw-2"], 2)
        ch.esfriar("fw-1")
        async with pool.vaga() as a:
            pass
        async with pool.vaga(evitar="fw-2") as b:   # a quente é a que acabou de falhar: ainda assim escolhe a melhor
            pass
        return a, b

    a, b = asyncio.run(cenario())
    assert a == "fw-2" and b == "fw-2", "a chave esfriando só é usada se não houver outra"


# ---------------------------------------------------------------- extração usando o rodízio
ANUNCIOS = [p.ResultadoWeb("Tinta Suvinil 18L", "https://t/a", "telhanorte.com.br", "Telhanorte", "R$ 739,90")]


class _Cli:
    """Cliente falso criado por chave: registra qual chave cada chamada usou."""
    chamadas: list = []
    roteiro: list = []

    def __init__(self, chave):
        self.chave = chave

    @property
    def chat(self):
        return NS(completions=NS(create=self._create))

    async def _create(self, model, **kw):
        _Cli.chamadas.append(self.chave)
        acao = _Cli.roteiro.pop(0)
        if isinstance(acao, Exception):
            raise acao
        if acao is None:
            return NS(choices=None, usage=None, error={"code": "failed_generation"})
        return NS(choices=[NS(message=NS(content=acao))], usage=NS(prompt_tokens=1, completion_tokens=1, cost=0))

    async def close(self):
        pass


def _http(status):
    return APIStatusError("x", response=httpx.Response(status, request=httpx.Request("POST", "http://x")), body=None)


@pytest.fixture
def clientes_por_chave(monkeypatch, tres_chaves):
    _Cli.chamadas, _Cli.roteiro = [], []
    monkeypatch.setattr(p, "_cliente", lambda chave=None: _Cli(chave))
    async def sem_espera(_):
        return None
    monkeypatch.setattr(p.asyncio, "sleep", sem_espera)
    return _Cli


def test_resposta_vazia_tenta_de_novo_em_outra_chave(clientes_por_chave):
    clientes_por_chave.roteiro = [None, "0|739.90|lata 18 L|SIM"]
    r = asyncio.run(p.extrair_e_conferir("Tinta Suvinil 18L", ANUNCIOS))
    assert r.conferidas and len(set(clientes_por_chave.chamadas)) == 2, clientes_por_chave.chamadas
    assert "fw-3" not in clientes_por_chave.chamadas, "a chave do agente não é usada na extração"


def test_429_esfria_a_chave(clientes_por_chave):
    clientes_por_chave.roteiro = [_http(429), "0|739.90|lata 18 L|SIM"]
    r = asyncio.run(p.extrair_e_conferir("Tinta Suvinil 18L", ANUNCIOS))
    primeira = clientes_por_chave.chamadas[0]
    assert ch._esfria_ate.get(primeira), "chave com 429 fica um tempo fora"
    assert r.conferidas and clientes_por_chave.chamadas[1] != primeira


# ---------------------------------------------------------------- reserva em paralelo quando o principal demora
class _ClienteLento:
    """Principal (Qwen3-32B) não responde nunca; a reserva responde na hora."""
    cancelado = False

    def __init__(self, chave):
        self.chave = chave

    @property
    def chat(self):
        return NS(completions=NS(create=self._create))

    async def _create(self, model, **kw):
        if "Qwen3-32B" in model:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                _ClienteLento.cancelado = True
                raise
        return NS(choices=[NS(message=NS(content="0|739.90|lata 18 L|SIM"))], usage=NS(prompt_tokens=1, completion_tokens=1, cost=0))

    async def close(self):
        pass


def test_principal_lento_dispara_a_reserva_em_paralelo_e_cancela_o_lento(monkeypatch, tres_chaves):
    monkeypatch.setattr(p, "_cliente", lambda chave=None: _ClienteLento(chave))
    monkeypatch.setattr(p, "get_settings", lambda: NS(pesquisa_hedge_s=0.05, pesquisa_modelo_extracao="Qwen/Qwen3-32B"))
    monkeypatch.setattr(p, "_indisponivel_ate", {})
    _ClienteLento.cancelado = False
    r = asyncio.run(asyncio.wait_for(p.extrair_e_conferir("Tinta Suvinil 18L", ANUNCIOS), timeout=3))
    assert r.modelo == p.MODELO_RESERVA_EXTRACAO and r.conferidas
    assert any("reserva em paralelo" in t for t in r.tentativas) and _ClienteLento.cancelado
