"""Etapa 4 — cálculo: embalagens, lista de compra com perda, preço comparável, outliers, confiança.
Os casos usam dados REAIS da avaliação da etapa 3 (docs/revisao/fatia-b.md)."""

from __future__ import annotations

import asyncio

import pytest

from src.calculo import calcular
from src.compra import Conteudo, conteudo_embalagem, qtd_embalagens
from src.modelos import ItemEntrada, ResultadoItem
from src.precos import Oferta, ResultadoExtracao


def of(loja, preco, emb, igual="sim"):
    return Oferta(loja=loja, dominio=f"{loja.lower().replace(' ', '')}.com.br", url=f"https://{loja}.com.br/{preco}",
                  titulo=loja, preco=preco, embalagem=emb, mesmo_produto=igual)


# ---------------------------------------------------------------- embalagens
@pytest.mark.parametrize("texto,esperado", [
    ("lata 18 L", Conteudo(18, "l")), ("galão 3,6 L", Conteudo(3.6, "l")), ("60 ml", Conteudo(0.06, "l")),
    ("caixa 2,16 m²", Conteudo(2.16, "m2")),          # regressão: era lida como 2 caixas de 16 m²
    ("caixa 1,8m²", Conteudo(1.8, "m2")), ("kit 2 latas 18 L", Conteudo(36, "l")), ("saco 20 kg", Conteudo(20, "kg")),
    ("barra 6 m", Conteudo(6, "m")), ("pacote 100 un", Conteudo(100, "un")), ("m²", Conteudo(1, "m2")),
    ("unidade", Conteudo(1, "un")), ("qualquer coisa", None), (None, None),
])
def test_entende_embalagens(texto, esperado):
    assert conteudo_embalagem(texto) == esperado


# ---------------------------------------------------------------- lista de compra
@pytest.mark.parametrize("produto,qtd,un,emb,n", [
    ("Tinta Suvinil Toque de Seda Branco Neve", 180, "m2", "lata 18 L", 2),      # 180/8 ×1,05 = 23,6 L
    ("Porcelanato Eliane Munari 60x60", 48, "m2", "caixa 1,8 m²", 30),            # 48 ×1,10 /1,8 = 29,3
    ("Argamassa Quartzolit AC-III", 48, "m2", "saco 20 kg", 13),                  # 48×5 ×1,05 /20 = 12,6
    ("Rejunte Quartzolit cinza platina", 68, "m2", "saco 5 kg", 5),               # 68×0,3 ×1,05 /5 = 4,3
    ("Ducha Lorenzetti Acqua Duo", 2, "un", "unidade", 2),
    ("Cabo flexível SIL 2,5 mm²", 300, "m", "rolo 100 m", 4),                     # 300 ×1,10 /100 = 3,3
])
def test_quantas_embalagens_comprar(produto, qtd, un, emb, n):
    assert qtd_embalagens(produto, qtd, un, conteudo_embalagem(emb))[0] == n


def test_conversao_impossivel_nao_chuta():
    n, _, motivo = qtd_embalagens("Bancada de granito", 3, "m2", conteudo_embalagem("unidade"))
    assert n is None and "converter" in motivo


# ---------------------------------------------------------------- cálculo
def test_porcelanato_com_preco_por_m2_e_por_caixa_fica_comparavel():
    """Caso real da avaliação: Leroy informou R$/m², Telhanorte R$/caixa 1,8 m²."""
    ext = ResultadoExtracao(ofertas=[of("Leroy Merlin", 97.9, "m²"), of("Telhanorte", 122.22, "caixa 1,8m²"),
                                     of("Ferreira Costa", 88.9, "m²"), of("Tumelero", 125.82, "caixa 1,8m²", "parecido")])
    c = calcular(ItemEntrada(id="1", descricao="Porcelanato Eliane Munari Cimento acetinado 60x60", quantidade=48, unidade="m2"), ext)
    assert c.embalagem == "caixa 1,8m²" and c.qtd_embalagens == 30
    assert (c.preco_un_min, c.preco_un_med, c.preco_un_max) == (67.9, 88.9, 97.9)       # R$/m²
    assert c.preco_emb_med == round(88.9 * 1.8, 2) and c.unidade_preco == "m2"
    assert len(c.fontes) == 3 and all(f.embalagem == "caixa 1,8m²" for f in c.fontes)   # parecido fica de fora


def test_preco_por_m2_rotulado_como_caixa_e_corrigido():
    """Achado real (etapa 8): Ferreira Costa R$ 88,90 POR m² veio do LLM como 'caixa 1,8 m²' e virou o mínimo."""
    ext = ResultadoExtracao(ofertas=[of("Leroy Merlin", 97.9, "m²"), of("Telhanorte", 122.22, "caixa 1,8m²"),
                                     of("Ferreira Costa", 88.9, "caixa 1,8 m²")])
    c = calcular(ItemEntrada(id="1", descricao="Porcelanato Eliane Munari Cimento acetinado 60x60", quantidade=48, unidade="m2"), ext)
    assert c.preco_un_min == 67.9, "o mínimo não pode ser o R$ 49,39/m² do rótulo errado"
    assert c.preco_un_med == 88.9 and c.descartadas.get("embalagem corrigida (preço avulso × embalagem)") == 1
    assert len(c.fontes) == 3


@pytest.mark.parametrize("preco_fc", [60.0, 120.0, 115.0])
def test_caixa_barata_que_nao_encaixa_como_preco_avulso_nao_e_corrigida(preco_fc):
    """60: lida como R$/m² ainda fica longe das outras (vira outlier, não correção).
    120 e 115: caixa ~30% mais barata é promoção plausível, não é suspeita (regressão do 1º desenho da trava)."""
    ext = ResultadoExtracao(ofertas=[of("Leroy Merlin", 97.9, "m²"), of("Magazine Luiza", 88.9, "m²"),
                                     of("Ferreira Costa", preco_fc, "caixa 1,8 m²")])
    c = calcular(ItemEntrada(id="1", descricao="Porcelanato Eliane Munari 60x60", quantidade=48, unidade="m2"), ext)
    assert "embalagem corrigida (preço avulso × embalagem)" not in c.descartadas


def test_preco_por_m2_que_parece_alto_nao_e_mexido():
    """A direção contrária é ambígua com 3 lojas: a Leroy em R$/m² não pode virar 'preço da caixa'."""
    ext = ResultadoExtracao(ofertas=[of("Leroy Merlin", 97.9, "m²"), of("Telhanorte", 122.22, "caixa 1,8m²"),
                                     of("Ferreira Costa", 88.9, "caixa 1,8 m²")])
    c = calcular(ItemEntrada(id="1", descricao="Porcelanato Eliane Munari 60x60", quantidade=48, unidade="m2"), ext)
    assert c.preco_un_max == 97.9


def test_tinta_usa_a_lata_do_item_e_nao_mistura_parecidos():
    ext = ResultadoExtracao(ofertas=[of("Telhanorte", 739.9, "lata 18 L"), of("Magazine Luiza", 849.0, "lata 18 L"),
                                     of("Mercado Livre", 189.0, "galão 3,6 L", "parecido"), of("Amazon", 1599.0, "kit 2 latas 18 L", "parecido")])
    c = calcular(ItemEntrada(id="1", descricao="Tinta Suvinil Toque de Seda Branco Neve 18L", quantidade=180, unidade="m2"), ext)
    assert (c.preco_emb_min, c.preco_emb_med, c.preco_emb_max) == (739.9, 794.45, 849.0)
    assert c.qtd_embalagens == 2 and c.premissa.startswith("rendimento")
    assert c.unidade_preco is None, "tinta em litros não vira R$/m² sem rendimento garantido"
    assert c.confianca == "media"   # 2 lojas, diferença 14%


def test_outlier_sai_da_media():
    ext = ResultadoExtracao(ofertas=[of("A", 50, "unidade"), of("B", 52, "unidade"), of("C", 49, "unidade"), of("D", 400, "unidade")])
    c = calcular(ItemEntrada(id="1", descricao="Registro Deca 3/4", quantidade=6, unidade="un"), ext)
    assert c.preco_emb_max == 52 and c.descartadas == {"preço fora da faixa (outlier)": 1}
    assert c.confianca == "alta" and c.qtd_embalagens == 6


def test_mesma_loja_conta_uma_vez_so():
    """Avaliação real: a Leroy apareceu 2× na argamassa (dois anúncios) e contava como duas lojas."""
    ext = ResultadoExtracao(ofertas=[of("Telhanorte", 46.9, "saco 20 kg"), of("Leroy Merlin", 48.9, "saco 20 kg"),
                                     of("Tumelero", 42.9, "saco 20 kg"), of("Leroy Merlin", 41.59, "saco 20 kg")])
    ext.ofertas[3].url += "-outro-anuncio"
    c = calcular(ItemEntrada(id="1", descricao="Argamassa Quartzolit AC-III cinza 20kg", quantidade=48, unidade="m2"), ext)
    assert [(f.loja, f.preco_embalagem) for f in c.fontes] == [("Telhanorte", 46.9), ("Leroy Merlin", 41.59), ("Tumelero", 42.9)]
    assert c.preco_emb_med == 42.9 and c.qtd_embalagens == 13
    assert c.descartadas == {"mesma loja (ficou a mais barata)": 1}


def test_generico_descarta_tinta_de_artesanato_e_vira_estimativa():
    """Caso real da avaliação: 'tinta vermelha' trouxe 60 ml, 250 ml e 120 ml de artesanato."""
    ext = ResultadoExtracao(ofertas=[of("Loja Suvinil", 290.9, "galão 3,6 L"), of("Amazon", 23.18, "60 ml", "parecido"),
                                     of("Mercado Livre", 54.22, "250 ml", "parecido"), of("Leroy Merlin", 89.9, "6 L", "parecido"),
                                     of("Amazon", 13.37, "120 ml", "parecido")])
    item = ItemEntrada(id="1", descricao="Tinta acrílica fosca vermelha", quantidade=12, unidade="m2",
                       classificacao="pendente_especificacao")
    c = calcular(item, ext)
    assert c.estimativa and c.descartadas.get("embalagem pequena (não é de obra)") == 3
    assert {f.loja for f in c.fontes} <= {"Loja Suvinil", "Leroy Merlin"}
    assert c.confianca != "alta"


def test_escolhe_a_embalagem_mais_barata_para_a_necessidade():
    """Avaliação real (etapa 6): tinta genérica para 12 m² (~1,6 L) saía como 1 latão de 18 L."""
    ext = ResultadoExtracao(ofertas=[of("Leroy Merlin", 299.0, "latão 18 L", "parecido"),
                                     of("Telhanorte", 309.0, "latão 18 L", "parecido"),
                                     of("Loja Suvinil", 79.9, "galão 3,6 L", "parecido")])
    item = ItemEntrada(id="1", descricao="Tinta acrílica fosca vermelha", quantidade=12, unidade="m2",
                       classificacao="pendente_especificacao")
    c = calcular(item, ext)
    assert c.embalagem == "galão 3,6 L" and c.qtd_embalagens == 1
    grande = calcular(item.model_copy(update={"quantidade": 400}), ext)   # 52,5 L: latas de 18 L saem mais em conta
    assert grande.embalagem == "latão 18 L" and grande.qtd_embalagens == 3


def test_sem_oferta_util_nao_inventa_preco():
    ext = ResultadoExtracao(ofertas=[of("A", 10, "algo estranho"), of("B", 99, "unidade", "nao")])
    c = calcular(ItemEntrada(id="1", descricao="Cuba Tramontina Morgana 56x34"), ext)
    assert not c.tem_preco and c.preco_emb_med is None and c.motivo


def test_resultado_encaixa_no_contrato_b_para_c():
    ext = ResultadoExtracao(ofertas=[of("Telhanorte", 739.9, "lata 18 L"), of("Magazine Luiza", 849.0, "lata 18 L")])
    c = calcular(ItemEntrada(id="1", descricao="Tinta Suvinil Toque de Seda 18L", quantidade=180, unidade="m2"), ext)
    r = ResultadoItem(item_id="1", status="definido", embalagem=c.embalagem, qtd_embalagens=c.qtd_embalagens,
                      preco_emb_min=c.preco_emb_min, preco_emb_med=c.preco_emb_med, preco_emb_max=c.preco_emb_max,
                      confianca=c.confianca, fontes=c.fontes, estimativa=c.estimativa)
    assert r.fontes[0].preco_embalagem == 739.9


# ---------------------------------------------------------------- real (busca + extração + cálculo)
@pytest.mark.real
def test_etapa4_ponta_a_ponta_real():
    from src.busca import buscar, montar_consulta
    from src.precos import extrair_e_conferir
    item = ItemEntrada(id="1", descricao="Tinta acrílica acetinada Suvinil Toque de Seda Branco Neve 18L", quantidade=180, unidade="m2")
    b = asyncio.run(buscar(montar_consulta(item)))
    e = asyncio.run(extrair_e_conferir(item.descricao, b.resultados))
    c = calcular(item, e)
    assert c.tem_preco, (c.motivo, [(o.loja, o.preco, o.embalagem, o.mesmo_produto) for o in e.ofertas])
    assert c.qtd_embalagens == 2 and c.embalagem
    assert 300 <= c.preco_emb_med <= 1500, f"preço fora do plausível para lata 18 L: {c.preco_emb_med}"
    assert c.preco_emb_min <= c.preco_emb_med <= c.preco_emb_max and c.fontes


# ---------------------------------------------------------------- material reconhecido pela marca/linha (achado no site, 07/11)
@pytest.mark.parametrize("produto,qtd,un,emb,n", [
    ("Suvinil T. Seda branco neve", 520, "m2", "latão 18 L", 4),          # 520/8 ×1,05 = 68,3 L → 4 latões
    ("Coral Decora cinza urbano", 40, "m2", "galão 3,6 L", 2),            # 40/8 ×1,05 = 5,25 L
    ("Quartzolit AC-III", 48, "m2", "saco 20 kg", 13),                    # argamassa: 5 kg/m²
    ("Votomassa AC-II", 48, "m2", "saco 20 kg", 13),                      # antes virava "massa" (0,6 kg/m²): 2 sacos
    ("Selador Coral", 100, "m2", "lata 18 L", 1),                         # continua selador (11 m²/L), não tinta
])
def test_material_reconhecido_pela_marca(produto, qtd, un, emb, n):
    assert qtd_embalagens(produto, qtd, un, conteudo_embalagem(emb))[0] == n


def test_falha_de_conversao_nao_vira_conta_na_tela():
    ext = ResultadoExtracao(ofertas=[of("Leroy Merlin", 2699.0, "unidade"), of("Mercado Livre", 1598.0, "unidade")])
    c = calcular(ItemEntrada(id="1", descricao="Vidro temperado 8 mm", quantidade=24, unidade="m2"), ext)
    assert c.tem_preco and c.qtd_embalagens is None and c.premissa is None
