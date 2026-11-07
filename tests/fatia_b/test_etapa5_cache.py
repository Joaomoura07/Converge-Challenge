"""Etapa 5 — cache de preços: chave estável, validade de 7 dias, vencido como reserva,
imagem estável e nunca derrubar a pesquisa."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

import src.cache as cache
from src.calculo import calcular
from src.modelos import ItemEntrada
from src.precos import Oferta, ResultadoExtracao

OFERTAS = [Oferta(loja="Telhanorte", dominio="telhanorte.com.br", url="https://t/a", titulo="Suvinil 18L",
                  preco=739.9, embalagem="lata 18 L", mesmo_produto="sim"),
           Oferta(loja="Magazine Luiza", dominio="magazineluiza.com.br", url="https://m/b", titulo="Suvinil 18L",
                  preco=849.0, embalagem="lata 18 L", mesmo_produto="sim")]
DESC = "Tinta Suvinil Toque de Seda Branco Neve 18L"


class SupabaseFalso:
    """Imita o encadeamento do supabase-py: table().select().eq().limit().execute() e table().upsert().execute()."""

    def __init__(self, erro: Exception | None = None):
        self.linhas: dict[str, dict] = {}
        self.erro = erro

    def table(self, nome):
        assert nome == "cache_precos"
        return _Consulta(self)


class _Consulta:
    def __init__(self, db): self.db, self.filtro, self.dados = db, None, None
    def select(self, *_): return self
    def limit(self, *_): return self
    def eq(self, _col, valor): self.filtro = valor; return self
    def upsert(self, linha, on_conflict=None): self.dados = linha; return self

    def execute(self):
        if self.db.erro:
            raise self.db.erro
        if self.dados is not None:
            self.db.linhas[self.dados["chave"]] = dict(self.dados)
            return NS(data=[self.dados])
        linha = self.db.linhas.get(self.filtro)
        return NS(data=[linha] if linha else [])


def _envelhecer(db, descricao, dias):
    linha = db.linhas[cache.chave_cache(descricao)]
    linha["atualizado_em"] = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()


# ---------------------------------------------------------------- chave
@pytest.mark.parametrize("a,b", [
    ("Tinta Suvinil Toque de Seda, Branco Neve 18 L", "tinta suvinil branco neve toque seda 18L"),
    ("Porcelanato Eliane Munari 60 x 60", "PORCELANATO ELIANE MUNARI 60X60"),
    ("Cabo flexível 2,5 mm²", "cabo flexivel 2.5mm2"),
])
def test_mesmo_produto_escrito_diferente_cai_na_mesma_chave(a, b):
    assert cache.chave_cache(a) == cache.chave_cache(b)


@pytest.mark.parametrize("a,b", [
    ("Tinta Suvinil Toque de Seda 18L", "Tinta Suvinil Toque de Seda 3,6L"),
    ("Cuba Tramontina Morgana 56x34", "Cuba Tramontina Morgana 69x49"),
    ("Cabo flexível 2,5 mm²", "Cabo flexível 4 mm²"),
])
def test_tamanho_diferente_e_outro_produto(a, b):
    assert cache.chave_cache(a) != cache.chave_cache(b)


# ---------------------------------------------------------------- ler / gravar
def test_grava_e_le_e_a_conta_e_refeita_para_a_quantidade_do_item():
    db = SupabaseFalso()
    ok = asyncio.run(cache.gravar(DESC, ResultadoExtracao(ofertas=OFERTAS, modelo="Qwen/Qwen3-32B"), "https://img/1.jpg",
                                  "tavily", cliente=db))
    assert ok
    e = asyncio.run(cache.ler("tinta suvinil toque seda branco neve 18 l", cliente=db))
    assert e and not e.vencido and e.imagem_url == "https://img/1.jpg" and e.extracao.ofertas == OFERTAS
    # o cache não guarda a conta: 180 m² e 400 m² do mesmo produto saem com quantidades diferentes
    c180 = calcular(ItemEntrada(id="1", descricao=DESC, quantidade=180, unidade="m2"), e.extracao)
    c400 = calcular(ItemEntrada(id="2", descricao=DESC, quantidade=400, unidade="m2"), e.extracao)
    assert (c180.qtd_embalagens, c400.qtd_embalagens) == (2, 3) and c180.preco_emb_med == c400.preco_emb_med


def test_vencido_so_volta_quando_pedido_como_reserva():
    db = SupabaseFalso()
    asyncio.run(cache.gravar(DESC, ResultadoExtracao(ofertas=OFERTAS), None, cliente=db))
    _envelhecer(db, DESC, 8)
    assert asyncio.run(cache.ler(DESC, cliente=db)) is None
    reserva = asyncio.run(cache.ler(DESC, aceitar_vencido=True, cliente=db))
    assert reserva and reserva.vencido and len(reserva.data_preco) == 5   # "dd/mm"


def test_imagem_fica_a_mesma_quando_o_preco_e_atualizado():
    """Pedido do Enzo: um produto, uma imagem — mesmo depois de pesquisar de novo."""
    db = SupabaseFalso()
    asyncio.run(cache.gravar(DESC, ResultadoExtracao(ofertas=OFERTAS), "https://img/primeira.jpg", cliente=db))
    _envelhecer(db, DESC, 8)
    anterior = asyncio.run(cache.ler(DESC, aceitar_vencido=True, cliente=db))
    asyncio.run(cache.gravar(DESC, ResultadoExtracao(ofertas=OFERTAS[:1]), "https://img/outra.jpg", anterior=anterior, cliente=db))
    e = asyncio.run(cache.ler(DESC, cliente=db))
    assert e.imagem_url == "https://img/primeira.jpg" and not e.vencido and len(e.extracao.ofertas) == 1


def test_nao_guarda_pesquisa_sem_preco():
    db = SupabaseFalso()
    sem_preco = [OFERTAS[0].model_copy(update={"preco": None})]
    assert not asyncio.run(cache.gravar(DESC, ResultadoExtracao(ofertas=sem_preco), "x", cliente=db))
    assert not db.linhas


@pytest.mark.parametrize("erro", [
    Exception("{'message': \"Could not find the table 'public.cache_precos' in the schema cache\", 'code': 'PGRST205'}"),
    ConnectionError("rede fora"),
])
def test_falha_do_banco_vira_cache_vazio_e_nao_derruba(erro):
    db = SupabaseFalso(erro=erro)
    assert asyncio.run(cache.ler(DESC, cliente=db)) is None
    assert asyncio.run(cache.gravar(DESC, ResultadoExtracao(ofertas=OFERTAS), None, cliente=db)) is False


def test_linha_corrompida_e_ignorada():
    db = SupabaseFalso()
    db.linhas[cache.chave_cache(DESC)] = {"chave": cache.chave_cache(DESC), "ofertas": [{"loja": "x"}], "atualizado_em": "ontem"}
    assert asyncio.run(cache.ler(DESC, aceitar_vencido=True, cliente=db)) is None


# ---------------------------------------------------------------- real (Supabase)
@pytest.mark.real
def test_etapa5_cache_real_no_supabase():
    from src.database import get_supabase
    sb = get_supabase()
    try:
        sb.table("cache_precos").select("chave").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"tabela cache_precos ainda não criada (rode sql/002_cache_precos.sql): {str(exc)[:80]}")
    desc = "TESTE revisao etapa5 produto sintetico 1L"
    try:
        assert asyncio.run(cache.gravar(desc, ResultadoExtracao(ofertas=OFERTAS), "https://img/teste.jpg", "tavily"))
        e = asyncio.run(cache.ler(desc))
        assert e and e.extracao.ofertas == OFERTAS and e.imagem_url == "https://img/teste.jpg" and not e.vencido
    finally:
        sb.table("cache_precos").delete().eq("chave", cache.chave_cache(desc)).execute()
