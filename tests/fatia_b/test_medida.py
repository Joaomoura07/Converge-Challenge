"""Aviso de medida: sinais por regra, frase pronta e a IA decidindo. Sem rede."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import pytest

from src import medida as m
from src.compra import Conteudo
from src.modelos import ItemEntrada


def item(desc, q=1, un="un"):
    return ItemEntrada(id="1", descricao=desc, quantidade=q, unidade=un)


def test_numero_sem_unidade_igual_a_embalagem_e_sinal():
    s = m.sinais_de_medida(item("Caixa d'água Fortlev 1000"), "1000 L", Conteudo(1000, "l"))
    assert len(s) == 1 and "«1000»" in s[0] and "1000 L" in s[0]


@pytest.mark.parametrize("desc", ["Caixa d'água Fortlev 1000 L", "Tinta Suvinil 18L", "Porcelanato 60x60", "Cabo SIL 2,5 mm"])
def test_medida_com_unidade_nao_e_sinal(desc):
    assert m.sinais_de_medida(item(desc), "1000 L", Conteudo(1000, "l")) == []


def test_pedido_em_m2_com_produto_vendido_em_unidades_e_sinal():
    s = m.sinais_de_medida(item("Nivelador Cortag", 11, "m2"), "kit 50 unidades", Conteudo(50, "un"))
    assert s and "m2" in s[0] and "unidades" in s[0]


def test_medida_assumida_sempre_avisa():
    s = m.sinais_de_medida(item("Reservatório Acme"), "500 L", Conteudo(500, "l"), medida_assumida=True)
    assert s and "confira" in s[0]


def test_sem_conteudo_nao_ha_o_que_conferir():
    assert m.sinais_de_medida(item("Coisa 1000"), None, None) == []


class Modelo:
    """Cliente falso: devolve a resposta combinada ou levanta erro."""
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.chamadas = resposta, erro, 0
        self.chat = NS(completions=NS(create=self._create))

    async def _create(self, **kw):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return NS(choices=[NS(message=NS(content=self.resposta))], usage=NS(cost=0.0001))


def rodar(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _chaves(monkeypatch):
    from contextlib import asynccontextmanager

    class Pool:
        @asynccontextmanager
        async def vaga(self, evitar=None):
            yield "k"
    monkeypatch.setattr(m.chaves_llm, "pool_extracao", lambda: Pool())


def test_a_ia_redige_o_aviso():
    cli = Modelo('{"aviso": "O pedido diz 1000 sem unidade; entendi 1000 L. Confira a descrição."}')
    r = rodar(m.aviso_de_medida(item("Caixa d'água Fortlev 1000"), "1000 L", Conteudo(1000, "l"), True, cliente=cli))
    assert r == "O pedido diz 1000 sem unidade; entendi 1000 L. Confira a descrição." and cli.chamadas == 1


def test_sem_modelo_vale_a_frase_pronta():
    cli = Modelo(erro=RuntimeError("sem chave"))
    r = rodar(m.aviso_de_medida(item("Caixa d'água Fortlev 1000"), "1000 L", Conteudo(1000, "l"), True, cliente=cli))
    assert r and "«1000»" in r and "Pesquisar de novo" in r


def test_a_ia_pode_dizer_que_a_medida_esta_certa_quando_nao_foi_assumida():
    cli = Modelo('{"aviso": null}')
    assert rodar(m.aviso_de_medida(item("Caixa d'água Fortlev 1000"), "1000 L", Conteudo(1000, "l"), False, cliente=cli)) is None


def test_sem_sinal_nem_chama_o_modelo():
    cli = Modelo('{"aviso": "x"}')
    assert rodar(m.aviso_de_medida(item("Tinta Suvinil 18L"), "lata 18 L", Conteudo(18, "l"), False, cliente=cli)) is None
    assert cli.chamadas == 0
