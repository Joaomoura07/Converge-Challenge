"""Busca aberta com a cidade/UF da obra (mais lojas por item) e anúncios com preço antes dos sem preço."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import pytest

import src.busca as b
import src.orcamento as o
from src.modelos import ItemEntrada

RECIFE = b.Local("Recife", "PE")


def W(titulo, url, trecho):
    return (titulo, url, trecho)


# ---------------------------------------------------------------- filtros
def test_aberta_so_aceita_loja_com_preco_escrito_e_uma_por_dominio():
    brutos = [
        W("Tinta Coral Decora 18L | Casa do Construtor", "https://www.casadoconstrutor.com.br/p/123", "R$ 459,90 à vista"),
        W("Tinta Coral Decora 18L", "https://www.casadoconstrutor.com.br/p/456", "R$ 470,00"),          # mesmo domínio
        W("Como escolher tinta", "https://blogdaobra.com.br/tinta", "Dicas para escolher a tinta"),      # sem preço
        W("Tinta Coral no YouTube", "https://youtube.com/watch?v=1", "R$ 400"),                           # bloqueado
        W("Busca tinta", "https://acmateriais.com.br/busca?q=tinta", "R$ 399"),                           # página de busca
        W("Tinta Coral Decora 18L", "https://www.leroymerlin.com.br/x", "R$ 499"),                        # lista fixa: outra busca
        W("Coral Decora 18 L - AC Materiais", "https://acmateriais.com.br/coral-decora-18l", "por R$ 445,00"),
    ]
    r = b._filtra_aberto(brutos, 5, None)
    assert [(x.dominio, x.loja) for x in r] == [("casadoconstrutor.com.br", "Casa do Construtor"),
                                                ("acmateriais.com.br", "AC Materiais")]


def test_loja_da_regiao_da_obra_sobe_na_lista():
    brutos = [W("Tinta Coral 18L | Loja SP", "https://lojasp.com.br/t", "R$ 450 entrega em São Paulo - SP"),
              W("Tinta Coral 18L | Materiais Boa Vista", "https://materiaisbv.com.br/t", "R$ 460 loja em Recife - PE")]
    assert [x.dominio for x in b._filtra_aberto(brutos, 5, RECIFE)] == ["materiaisbv.com.br", "lojasp.com.br"]
    assert [x.dominio for x in b._filtra_aberto(brutos, 5, None)] == ["lojasp.com.br", "materiaisbv.com.br"]


@pytest.mark.parametrize("dominio,titulo,nome", [
    ("www.casadoconstrutor.com.br", "Tinta | Casa do Construtor", "Casa do Construtor"),
    ("loja.acmateriais.com.br", "Tinta Coral 18L 2024", "Acmateriais"),
    ("lojaeletrica.com.br", "Tomada Liz 10A - material elétrico", "Lojaeletrica"),   # fim do título é categoria
    ("tintasbrasil.com.br", "Tinta 18L | SP", "Tintasbrasil"),
    ("deposito-sao-jose.com.br", "Tinta - Promoção 50% off", "Deposito Sao Jose"),
])
def test_nome_da_loja(dominio, titulo, nome):
    assert b.nome_da_loja(dominio, titulo) == nome


def test_lista_fixa_poe_anuncio_com_preco_antes_do_sem_preco():
    """Achado de 07/11: a Leroy Merlin vem sem preço (carregado por JavaScript) e tomava a vaga de quem tem preço."""
    brutos = [W("Tinta 18L", "https://www.leroymerlin.com.br/a", "Compre online"),
              W("Tinta 18L", "https://www.telhanorte.com.br/b", "R$ 739,90"),
              W("Tinta 18L", "https://www.cec.com.br/c", "R$ 750,00")]
    assert [x.loja for x in b._filtra(brutos, 2)] == ["Telhanorte", "C&C"]
    assert [x.loja for x in b._filtra(brutos, 5)] == ["Telhanorte", "C&C", "Leroy Merlin"]


def test_consulta_regional():
    assert b.consulta_regional("tinta coral preço", RECIFE) == "tinta coral preço Recife PE"
    assert b.consulta_regional("tinta coral preço", None) == "tinta coral preço"


# ---------------------------------------------------------------- junção das duas buscas
def _resp(provedor, lojas, imagens=()):
    return b.RespostaBusca("q", provedor, [b.ResultadoWeb(l, f"https://{l}.com.br/p", f"{l}.com.br", l, "R$ 10") for l in lojas],
                           [b.ImagemWeb(i) for i in imagens])


@pytest.fixture
def sem_imagem(monkeypatch):
    async def nenhuma(imagens, produto, *a, **k):
        return imagens[0].url if imagens else None
    monkeypatch.setattr(b, "escolher_imagem_verificada", nenhuma)


def test_buscar_junta_fixa_e_aberta_e_usa_o_local_da_obra(monkeypatch, sem_imagem):
    visto = {}

    async def fixa(consulta, limite, rodizio):
        return _resp("tavily", ["Telhanorte"])

    async def aberta(consulta, limite, rodizio, local):
        visto["local"] = local
        return _resp("tavily", ["Casa X", "Loja Y"], ["https://img/aberta.jpg"])

    monkeypatch.setattr(b, "_buscar_fixa", fixa)
    monkeypatch.setattr(b, "_buscar_aberta", aberta)

    async def cenario():
        with b.na_regiao(RECIFE):
            # dentro de tarefas (como no gather da pesquisa) o local continua valendo
            return (await asyncio.gather(b.buscar("q", rodizio=b._RodizioChaves(["k"]))))[0]

    r = asyncio.run(cenario())
    assert [x.loja for x in r.resultados] == ["Telhanorte", "Casa X", "Loja Y"] and visto["local"] == RECIFE
    assert r.imagem == "https://img/aberta.jpg", "sem imagem da fixa, usa a da aberta"
    assert b.LOCAL_DA_OBRA.get() is None, "o local não vaza para fora do orçamento"


def test_busca_aberta_falha_nao_derruba_a_fixa(monkeypatch, sem_imagem):
    async def fixa(consulta, limite, rodizio):
        return _resp("tavily", ["Telhanorte"])

    async def tav(*a):
        raise TimeoutError()

    async def ddg(*a):
        raise ConnectionError()

    monkeypatch.setattr(b, "_buscar_fixa", fixa)
    monkeypatch.setattr(b, "_tavily_aberto", tav)
    monkeypatch.setattr(b, "_duckduckgo_aberto", ddg)
    r = asyncio.run(b.buscar("q", rodizio=b._RodizioChaves(["k"])))
    assert [x.loja for x in r.resultados] == ["Telhanorte"] and r.erro is None


def test_busca_aberta_desligada(monkeypatch, sem_imagem):
    async def fixa(consulta, limite, rodizio):
        return _resp("tavily", ["Telhanorte"])

    async def aberta(*a):
        raise AssertionError("não devia buscar")

    monkeypatch.setattr(b, "_buscar_fixa", fixa)
    monkeypatch.setattr(b, "_buscar_aberta", aberta)
    monkeypatch.setattr(b, "get_settings", lambda: NS(pesquisa_busca_aberta=False, pesquisa_max_lojas=5))
    assert len(asyncio.run(b.buscar("q", rodizio=b._RodizioChaves(["k"]))).resultados) == 1


def test_tavily_aberto_usa_brasil_e_exclui_a_lista_fixa(monkeypatch):
    import tavily
    chamadas = {}

    class Falso:
        def __init__(self, api_key): pass
        async def search(self, q, **kw):
            chamadas.update(kw, q=q)
            return {"results": [{"title": "Tinta | Casa X", "url": "https://casax.com.br/p", "content": "R$ 10"}], "images": []}

    monkeypatch.setattr(tavily, "AsyncTavilyClient", Falso)
    r = asyncio.run(b._tavily_aberto("tinta preço", 4, b._RodizioChaves(["k"]), RECIFE))
    assert chamadas["q"] == "tinta preço Recife PE" and chamadas["country"] == "brazil"
    assert "leroymerlin.com.br" in chamadas["exclude_domains"] and "youtube.com" in chamadas["exclude_domains"]
    assert "include_domains" not in chamadas and r.resultados[0].loja == "Casa X"


# ---------------------------------------------------------------- CEP da obra → cidade/UF
class _ViaCEP:
    respostas: dict = {}

    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def get(self, url):
        cep = url.split("/ws/")[1].split("/")[0]
        r = _ViaCEP.respostas[cep]
        if isinstance(r, Exception):
            raise r
        return NS(json=lambda: r)


@pytest.fixture
def viacep(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _ViaCEP)
    monkeypatch.setattr(b, "_locais", {})
    _ViaCEP.respostas = {"52011050": {"localidade": "Recife", "uf": "PE"}, "00000000": {"erro": True},
                         "11111111": ConnectionError("sem rede")}
    return _ViaCEP


@pytest.mark.parametrize("cep,esperado", [("52011-050", RECIFE), ("52011050", RECIFE), ("00000000", None),
                                          ("11111111", None), ("123", None), (None, None)])
def test_local_do_cep(viacep, cep, esperado):
    assert asyncio.run(b.local_do_cep(cep)) == esperado


def test_falha_de_rede_no_viacep_nao_fica_guardada(viacep):
    asyncio.run(b.local_do_cep("11111111"))
    assert "11111111" not in b._locais


def test_pesquisar_orcamento_pesquisa_na_regiao_do_cep(viacep, monkeypatch):
    locais = []

    async def pesquisar_itens(itens, ao_terminar=None, **kw):
        locais.append(b.LOCAL_DA_OBRA.get())
        return []

    class Banco:
        async def reservar(self, oid): return True
        async def cep(self, oid): return "52011050"
        async def itens_para_pesquisar(self, oid): return [ItemEntrada(id="1", descricao="Tinta")]
        async def gravar_item(self, r): pass
        async def concluir(self, oid, erro=None, custo_usd=None): pass

    monkeypatch.setattr(o, "pesquisar_itens", pesquisar_itens)
    monkeypatch.setattr(o, "GANCHOS_FIM", [])
    asyncio.run(o.pesquisar_orcamento("orc-1", banco=Banco()))
    assert locais == [RECIFE]


def test_busca_aberta_lenta_nao_segura_o_item(monkeypatch, sem_imagem):
    """Medido em 07/11: a aberta chegou a 10 s e o 1º item foi de ~6 s para 20 s. Passou do prazo, segue com a fixa."""
    async def fixa(consulta, limite, rodizio):
        return _resp("tavily", ["Telhanorte"])

    async def aberta_lenta(*a):
        await asyncio.Event().wait()

    monkeypatch.setattr(b, "_buscar_fixa", fixa)
    monkeypatch.setattr(b, "_buscar_aberta", aberta_lenta)
    monkeypatch.setattr(b, "get_settings", lambda: NS(pesquisa_busca_aberta=True, pesquisa_max_lojas=5, pesquisa_max_abertas=4,
                                                      pesquisa_max_anuncios=8, pesquisa_prazo_aberta_s=0.05))
    r = asyncio.run(asyncio.wait_for(b.buscar("q", rodizio=b._RodizioChaves(["k"])), timeout=2))
    assert [x.loja for x in r.resultados] == ["Telhanorte"]


def test_lista_fixa_com_2_precos_nao_espera_a_aberta(monkeypatch, sem_imagem):
    """Item fácil não espera a busca aberta (o 1º item na tela tinha ido de ~6 s para 12–20 s)."""
    cancelada = []

    async def fixa(consulta, limite, rodizio):
        return _resp("tavily", ["Telhanorte", "C&C"])          # 2 anúncios com "R$"

    async def aberta_lenta(*a):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelada.append(True)
            raise

    monkeypatch.setattr(b, "_buscar_fixa", fixa)
    monkeypatch.setattr(b, "_buscar_aberta", aberta_lenta)
    r = asyncio.run(asyncio.wait_for(b.buscar("q", rodizio=b._RodizioChaves(["k"])), timeout=1))
    assert [x.loja for x in r.resultados] == ["Telhanorte", "C&C"], "voltou sem esperar a aberta (timeout de 1 s)"
