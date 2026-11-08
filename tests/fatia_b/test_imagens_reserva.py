"""Fotos: recuperação sem LLM, falhas isoladas e evidência da variante original."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import busca as b, imagens

PRODUTO = "Porcelanato Eliane Munari Cimento acetinado 60x60"
BOA = b.ImagemWeb("https://loja.example/porcelanato-eliane-munari-cimento-60x60.jpg", PRODUTO)


@pytest.mark.parametrize("url", [None, "", "data:image/png;base64,x", "javascript:alert(1)",
    "http://127.0.0.1/x", "http://192.168.1.2/x", "https://user:pass@loja.example/x", "https://loja.local/x"])
def test_url_insegura_nao_vira_candidata(url):
    assert imagens.normalizar_url_imagem(url) is None


def test_corrige_template_magalu_sem_alterar_query_assinada():
    url = "http://a-static.mlcdn.com.br/%7Bw%7Dx%7Bh%7D/produto.jpg?v=a%2Fb"
    assert imagens.normalizar_url_imagem(url) == "https://a-static.mlcdn.com.br/600x600/produto.jpg?v=a%2Fb"
    assert imagens.normalizar_url_imagem("//cdn.example/foto.webp") == "https://cdn.example/foto.webp"


def test_duplicadas_nao_esgotam_tentativas_e_excecao_nao_derruba_outras():
    ruim = b.ImagemWeb(BOA.url.replace(".jpg", "-produto.jpg"), PRODUTO)
    vistas = []
    async def checar(url):
        vistas.append(url)
        if url == ruim.url:
            raise TimeoutError()
        return True
    assert asyncio.run(b.escolher_imagem_verificada([ruim] * 8 + [BOA], PRODUTO, checar)) == BOA.url
    assert len(vistas) == 2


def test_tenta_quarta_imagem_quando_as_primeiras_falham():
    candidatas = [b.ImagemWeb(BOA.url.replace(".jpg", f"-{i}.jpg"), PRODUTO) for i in range(6)]
    ultima = b._candidatas(candidatas, PRODUTO)[-1].url
    async def checar(url):
        return url == ultima
    assert asyncio.run(b.escolher_imagem_verificada(candidatas, PRODUTO, checar)) == ultima


def test_miniatura_preserva_medida_incompativel_da_url_original():
    dados = {"images": [{"title": "Cuba Tramontina Morgana 56x34",
                         "imageUrl": "https://loja.example/cuba-tramontina-morgana-69x49.jpg",
                         "thumbnailUrl": "https://encrypted-tbn0.gstatic.com/images?q=1"}]}
    candidatas = imagens.ler_imagens_serper(dados)
    assert len(candidatas) == 2
    assert b.escolher_imagem(candidatas, "Cuba Tramontina Morgana 56x34") is None


def test_ler_reserva_ignora_respostas_incompletas_e_logos():
    dados = {"images": [None, {}, {"imageUrl": BOA.url},
        {"title": PRODUTO, "imageUrl": "https://loja.example/logo.png"},
        {"title": PRODUTO, "imageUrl": BOA.url}]}
    assert imagens.ler_imagens_serper(dados) == [BOA]


def test_reserva_recupera_miniatura_quando_original_bloqueia(monkeypatch):
    mini = "https://encrypted-tbn0.gstatic.com/images?q=1"
    novas = imagens.ler_imagens_serper({"images": [{"title": PRODUTO, "imageUrl": BOA.url, "thumbnailUrl": mini}]})
    monkeypatch.setattr(imagens, "buscar_imagens_reserva", AsyncMock(return_value=novas))
    escolher = b.escolher_imagem_verificada
    async def checar(url):
        return url == mini
    async def escolha(candidatas, consulta, **kwargs):
        return await escolher(candidatas, consulta, checar=checar, **kwargs)
    monkeypatch.setattr(b, "escolher_imagem_verificada", escolha)
    r = b.RespostaBusca(PRODUTO, "serper")
    asyncio.run(imagens.completar_imagem(r, PRODUTO))
    assert r.imagem == mini and len(r.imagens) == 2


def test_timeout_da_reserva_preserva_resultados(monkeypatch):
    async def demorada(*_):
        await asyncio.sleep(10)
    monkeypatch.setattr(imagens, "buscar_imagens_reserva", demorada)
    monkeypatch.setattr(imagens, "PRAZO_RESERVA_S", 0.01)
    r = b.RespostaBusca(PRODUTO, "tavily", resultados=["resultado preservado"])
    asyncio.run(imagens.completar_imagem(r, PRODUTO))
    assert r.imagem is None and r.resultados == ["resultado preservado"]


def test_sem_chave_nao_dispara_serper(monkeypatch):
    chamar = AsyncMock()
    monkeypatch.setattr(imagens.serper, "post", chamar)
    assert asyncio.run(imagens.buscar_imagens_reserva(PRODUTO)) == []
    chamar.assert_not_called()


def test_busca_mescla_imagem_aberta_mesmo_com_candidata_fixa_ruim(monkeypatch):
    monkeypatch.setattr(b.get_settings(), "pesquisa_busca_aberta", True)
    fixa = b.RespostaBusca(PRODUTO, "tavily", imagens=[b.ImagemWeb("https://loja.example/logo.png", PRODUTO)])
    monkeypatch.setattr(b, "_buscar_fixa", AsyncMock(return_value=fixa))
    monkeypatch.setattr(b, "_buscar_aberta", AsyncMock(return_value=b.RespostaBusca(PRODUTO, "tavily", imagens=[BOA])))
    monkeypatch.setattr(b, "_buscar_regional", AsyncMock(return_value=b.RespostaBusca(PRODUTO, "nenhum")))
    async def escolha(candidatas, produto):
        return b.escolher_imagem(candidatas, produto)
    monkeypatch.setattr(b, "escolher_imagem_verificada", escolha)
    reserva = AsyncMock()
    monkeypatch.setattr(b, "completar_imagem", reserva)
    r = asyncio.run(b.buscar(PRODUTO))
    assert r.imagem == BOA.url
    reserva.assert_not_called()


def test_busca_chama_reserva_so_quando_nao_tem_foto_valida(monkeypatch):
    monkeypatch.setattr(b.get_settings(), "pesquisa_busca_aberta", False)
    monkeypatch.setattr(b, "_buscar_fixa", AsyncMock(return_value=b.RespostaBusca(PRODUTO, "duckduckgo")))
    monkeypatch.setattr(b, "escolher_imagem_verificada", AsyncMock(return_value=None))
    reserva = AsyncMock()
    monkeypatch.setattr(b, "completar_imagem", reserva)
    asyncio.run(b.buscar(PRODUTO))
    reserva.assert_awaited_once()


def test_busca_aberta_nao_perde_foto_ao_usar_reserva_textual(monkeypatch):
    monkeypatch.setattr(b, "_tavily_aberto", AsyncMock(return_value=b.RespostaBusca(PRODUTO, "tavily", imagens=[BOA])))
    monkeypatch.setattr(b, "_serper_aberto", AsyncMock(return_value=b.RespostaBusca(PRODUTO, "serper", resultados=["loja"])))
    r = asyncio.run(b._buscar_aberta(PRODUTO, 3, b._RodizioChaves([]), None))
    assert r.imagens == [BOA] and r.resultados == ["loja"]


def test_cache_sem_imagem_recupera_foto_sem_refazer_precos(monkeypatch):
    from src import cache
    entrada = SimpleNamespace(imagem_url=None)
    async def completar(r, _):
        r.imagem = BOA.url
    monkeypatch.setattr(imagens, "completar_imagem", completar)
    gravar = AsyncMock()
    monkeypatch.setattr(cache, "gravar", gravar)
    assert asyncio.run(imagens.imagem_do_cache(entrada, PRODUTO)) == BOA.url
    gravar.assert_not_called()


def test_cache_com_foto_nao_gasta_busca(monkeypatch):
    reserva = AsyncMock()
    monkeypatch.setattr(imagens, "completar_imagem", reserva)
    assert asyncio.run(imagens.imagem_do_cache(SimpleNamespace(imagem_url=BOA.url), PRODUTO)) == BOA.url
    reserva.assert_not_called()
