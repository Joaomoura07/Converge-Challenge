"""Correções de 08/11 (véspera da demo): chave do Serper sem crédito, classe AC trocada e link que abre no Google."""

from __future__ import annotations

import asyncio

import httpx
import pytest

import src.serper as serper
from src.google_shopping import (DOMINIO_SHOPPING, ler_anuncios, link_do_google, mesmo_codigo, priorizar_links_diretos,
                                 semelhanca)
from src.precos import Oferta

LINK_GOOGLE = "https://www.google.com/search?ibp=oshop&q=Argamassa&prds=localAnnotatedOffer"


def of(loja, url, dominio, preco=46.9, igual="sim"):
    return Oferta(loja=loja, dominio=dominio, url=url, titulo="Argamassa ACIII 20kg Quartzolit", preco=preco,
                  embalagem="20 kg", mesmo_produto=igual)


# ---------------------------------------------------------------- chave sem crédito (HTTP 400)
class _Cliente:
    def __init__(self, respostas): self.respostas, self.chaves = respostas, []

    async def post(self, url, headers, json):
        self.chaves.append(headers["X-API-KEY"])
        status, corpo = self.respostas[headers["X-API-KEY"]]
        return httpx.Response(status, json=corpo, request=httpx.Request("POST", url))


def test_chave_sem_credito_400_passa_para_a_proxima_e_fica_de_lado(monkeypatch):
    """Medido em 08/11: a 1ª chave respondia 400 "Not enough credits" e o código desistia: nenhum anúncio, nenhuma foto."""
    monkeypatch.setattr(serper, "_esgotadas", set())
    cli = _Cliente({"k1": (400, {"message": "Not enough credits", "statusCode": 400}), "k2": (200, {"shopping": [1]})})
    assert asyncio.run(serper.post(cli, "https://x", {}, ["k1", "k2"])) == {"shopping": [1]}
    assert asyncio.run(serper.post(cli, "https://x", {}, ["k1", "k2"])) == {"shopping": [1]}
    assert cli.chaves == ["k1", "k2", "k2"], "a chave esgotada não deve ser tentada de novo"


def test_400_de_consulta_ruim_nao_queima_a_chave(monkeypatch):
    monkeypatch.setattr(serper, "_esgotadas", set())
    cli = _Cliente({"k1": (400, {"message": "Query too long"})})
    assert asyncio.run(serper.post(cli, "https://x", {}, ["k1"])) is None
    assert serper._esgotadas == set()


# ---------------------------------------------------------------- classe AC
@pytest.mark.parametrize("titulo,igual", [
    ("Argamassa Cimentocola ACIII 20Kg Cinza Quartzolit", True),
    ("Argamassa AC-III Quartzolit 20kg", True),
    ("Argamassa AC3 Quartzolit 20kg", True),
    ("Argamassa Cimentcola Interno ACI 20kg Quartzolit", False),   # R$ 14,90 entrava na média da AC-III
    ("Argamassa Quartzolit Cozinhas e Banheiros 20kg", False),     # R$ 16,06, sem classe
])
def test_classe_da_argamassa_precisa_ser_a_mesma(titulo, igual):
    item = "Argamassa Quartzolit AC-III 20kg"
    assert mesmo_codigo(item, titulo) is igual
    assert (semelhanca(item, titulo) > 0) is igual


def test_item_sem_classe_nao_exige_classe():
    assert mesmo_codigo("Tinta Suvinil Toque de Seda 18L", "Tinta Suvinil Toque de Seda Branco 18L")


def test_preco_vazio_descarta_o_anuncio():
    anuncios = [{"title": "Argamassa ACIII 20kg Quartzolit", "source": "Telhanorte", "price": None},
                {"title": "Argamassa ACIII 20kg Quartzolit", "source": "Leroy Merlin", "price": "sob consulta"},
                {"title": "Argamassa ACIII 20kg Quartzolit", "source": "C&C", "price": "R$ 46,90 agora"}]
    ofertas = ler_anuncios("Argamassa Quartzolit AC-III 20kg", "m2", anuncios, generico=False)
    assert [(o.loja, o.preco) for o in ofertas] == [("C&C", 46.9)]


# ---------------------------------------------------------------- link direto da loja
def test_loja_da_regiao_com_link_do_google_conta_como_link_do_google():
    """A oferta regional levava o domínio da loja e o link do Google: a tela abria o Google pelo nome da loja."""
    assert link_do_google(of("Ferreira Costa", LINK_GOOGLE, "ferreiracosta.com"))
    assert link_do_google(of("Baratão", "https://www.google.com/search?tbm=shop&q=x", DOMINIO_SHOPPING))
    assert not link_do_google(of("Leroy Merlin", "https://www.leroymerlin.com.br/argamassa", "leroymerlin.com.br"))


def test_com_lojas_de_link_direto_o_google_sai():
    ofertas = [of("Leroy Merlin", "https://www.leroymerlin.com.br/a", "leroymerlin.com.br"),
               of("Telhanorte", LINK_GOOGLE, DOMINIO_SHOPPING), of("Ferreira Costa", LINK_GOOGLE + "2", "ferreiracosta.com")]
    assert [o.loja for o in priorizar_links_diretos(ofertas, outras_diretas=1)] == ["Leroy Merlin"]


def test_sem_loja_direta_o_preco_do_google_fica_mas_sem_fingir_ser_da_loja():
    ofertas = [of("Telhanorte", LINK_GOOGLE, DOMINIO_SHOPPING), of("Ferreira Costa", LINK_GOOGLE + "2", "ferreiracosta.com")]
    saida = priorizar_links_diretos(ofertas, outras_diretas=0)
    assert len(saida) == 2 and all(o.dominio == DOMINIO_SHOPPING for o in saida)


@pytest.mark.real
def test_serper_real_responde_com_alguma_chave():
    from src.google_shopping import ofertas_google
    ofertas = asyncio.run(ofertas_google("Argamassa Quartzolit AC-III 20kg", "m2"))
    assert ofertas, "nenhum anúncio: todas as chaves do Serper sem crédito?"
    assert all(o.preco and mesmo_codigo("Argamassa Quartzolit AC-III 20kg", o.titulo) for o in ofertas)
    assert any(o.imagem for o in ofertas), "o Shopping devolve imageUrl"
