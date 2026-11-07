"""Etapa 9 — pré-aquecimento do cache para a demo: lê o arquivo da obra, pesquisa tudo e deixa no cache
os itens lentos (os que precisaram do agente), tirando os rápidos para chegarem ao vivo."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import scripts.aquecer_cache as aq
from src.modelos import ItemEntrada, ResultadoItem, Fonte

COZINHA = Path(__file__).resolve().parents[2] / "docs" / "arquivos-teste" / "03-cozinha-gracas"


def test_metricas_do_pitch_contam_certo():
    from scripts.metricas_pitch import resumir, tabela
    from src.modelos import Fonte, ResultadoItem
    f = [Fonte(loja=l, dominio=f"{l}.com.br", url=f"https://{l}", preco_embalagem=10) for l in "abc"]
    rs = [ResultadoItem(item_id="1", status="definido", preco_emb_min=10, preco_emb_med=10, preco_emb_max=10, fontes=f),
          ResultadoItem(item_id="2", status="definido", preco_emb_min=10, preco_emb_med=10, preco_emb_max=10,
                        fontes=f[:1], iteracoes=2),
          ResultadoItem(item_id="3", status="pendente_especificacao", pergunta="Qual marca?"),
          ResultadoItem(item_id="4", status="nao_encontrado", motivo="nada")]
    m = resumir(rs, 1.6, 30.0, 0.02)
    assert (m.itens, m.com_preco, m.definidos, m.pendentes, m.nao_encontrados, m.agente_refez) == (4, 2, 2, 1, 1, 1)
    assert m.lojas_media == 2.0
    t = tabela(m, "teste")
    assert "| Com preço e fonte (resolvidos sozinhos) | 2 (50%) |" in t and "1.6 s" in t and "US$ 0.0050 por item" not in t
    assert "US$ 0.00500 por item" in t


def test_le_o_json_de_orcamento_da_cozinha():
    itens = aq.ler_itens(COZINHA / "orcamento_cozinha-gracas.json")
    assert len(itens) == 24 and itens[0].descricao == "Coral Decora cinza urbano"
    assert itens[0].quantidade == 22.0 and itens[0].unidade == "m²"


def test_le_o_csv_do_excel_em_windows_1252():
    itens = aq.ler_itens(COZINHA / "lista_materiais_cozinha-gracas.csv")
    assert len(itens) == 24
    assert itens[0].unidade == "m²", "acento do Windows-1252 precisa sobreviver"
    assert any("metrô" in i.descricao for i in itens)


@pytest.mark.parametrize("v,esperado", [("22", 22.0), ("12,5", 12.5), ("1.234,5", 1234.5), (3, 3.0), ("", None), ("verificar", None)])
def test_numero_em_formato_brasileiro(v, esperado):
    assert aq._numero(v) == esperado


def _medida(i, seg, com_preco=True):
    item = ItemEntrada(id=str(i), descricao=f"produto {i}")
    if com_preco:
        r = ResultadoItem(item_id=str(i), status="definido", preco_emb_min=10, preco_emb_med=10, preco_emb_max=10,
                          fontes=[Fonte(loja="A", dominio="a.com.br", url="https://a", preco_embalagem=10)])
    else:
        r = ResultadoItem(item_id=str(i), status="nao_encontrado", motivo="x")
    return aq.Medida(item, r, seg)


def test_apaga_os_rapidos_e_mantem_os_lentos():
    medidas = [_medida(1, 7.0), _medida(2, 55.0), _medida(3, 8.0), _medida(4, 9.5), _medida(5, 3.0, com_preco=False)]
    apagar = aq.escolher_para_apagar(medidas, 0.5)
    assert [m.item.id for m in apagar] == ["1", "3"], "os 2 mais rápidos COM preço saem; o de 55 s (agente) fica"
    assert aq.escolher_para_apagar(medidas, 1.0) == []
    assert len(aq.escolher_para_apagar(medidas, 0.0)) == 4


def test_aquecer_pesquisa_sem_cache_e_apaga_a_parte_ao_vivo(monkeypatch):
    chamadas, apagados = {}, []

    async def pesquisar_itens(itens, ao_terminar=None, **kw):
        chamadas.update(kw)
        rs = [_medida(i.id, 0).resultado for i in itens]
        for r in rs:
            await ao_terminar(r)
        return rs

    async def apagar(desc, cliente=None):
        apagados.append(desc)
        return True

    monkeypatch.setattr(aq, "pesquisar_itens", pesquisar_itens)
    monkeypatch.setattr(aq.cache, "apagar", apagar)
    itens = [ItemEntrada(id=str(n), descricao=f"produto {n}") for n in range(1, 7)]
    medidas, fora, _ = asyncio.run(aq.aquecer(itens, 0.5))
    assert chamadas["usar_cache"] is False and chamadas["usar_agente"] is True
    assert len(fora) == 3 and len(apagados) == 3 and len(medidas) == 6


def test_cep_da_obra_vem_do_json_de_orcamento():
    assert aq.cep_do_arquivo(COZINHA / "orcamento_cozinha-gracas.json") == "52011-050"
    assert aq.cep_do_arquivo(COZINHA / "lista_materiais_cozinha-gracas.csv") is None


@pytest.mark.parametrize("arquivo,n", [("apto-boa-viagem", 47), ("casa-terrea-aldeia", 53), ("escritorio-ilha-do-leite", 33)])
def test_le_os_tres_exemplos_do_site(arquivo, n):
    """São os arquivos do botão 'Usar arquivo de exemplo' (o que o jurado testa): o aquecimento precisa ler todos,
    inclusive o do escritório, que tem cabeçalho em inglês (Category,Description,Unit,Qty)."""
    itens = aq.ler_itens(COZINHA.parents[2] / "frontend" / "public" / "exemplos" / f"{arquivo}.csv")
    assert len(itens) == n and all(i.descricao and i.quantidade for i in itens)
