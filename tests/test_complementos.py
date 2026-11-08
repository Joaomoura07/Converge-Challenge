"""Testes da E2 (itens esquecidos) — dados falsos, sem rede."""

import json
from pathlib import Path

from src.complementos import sugerir_complementos

ROOT = Path(__file__).resolve().parent.parent


def _por_desc(res, trecho):
    return [c for c in res if trecho.lower() in c.descricao.lower()]


def test_porcelanato_48m2_sugere_15_argamassa_e_5_rejunte():
    itens = [{"linha": 3, "categoria": "Revestimentos", "descricao": "Porcelanato 90x90 acetinado",
              "quantidade": 48, "unidade": "m²"}]
    res = sugerir_complementos(itens)
    assert _por_desc(res, "AC-III")[0].quantidade == 15
    assert _por_desc(res, "Rejunte")[0].quantidade == 5
    assert _por_desc(res, "nivelador")[0].quantidade == 3
    assert all(c.origem_linhas == [3] and c.estimativa for c in res)


def test_nao_repete_o_que_ja_esta_na_lista():
    itens = [
        {"linha": 1, "descricao": "Porcelanato 60x60", "quantidade": 20, "unidade": "m2"},
        {"linha": 2, "descricao": "Argamassa AC-III 20 kg", "quantidade": 10, "unidade": "un"},
    ]
    res = sugerir_complementos(itens)
    assert not _por_desc(res, "argamassa")
    assert _por_desc(res, "rejunte")


def test_soma_varios_itens_da_mesma_regra():
    itens = [
        {"linha": 1, "descricao": "Porcelanato sala", "quantidade": 30, "unidade": "m2"},
        {"linha": 2, "descricao": "Revestimento parede cozinha", "quantidade": 18, "unidade": "m2"},
    ]
    res = sugerir_complementos(itens)
    assert _por_desc(res, "AC-III")[0].quantidade == 15  # 48 m²
    assert _por_desc(res, "AC-III")[0].origem_linhas == [1, 2]


def test_pintura_em_m2_e_em_litros():
    m2 = sugerir_complementos([{"linha": 1, "categoria": "Pintura", "descricao": "Tinta acrílica",
                                "quantidade": 180, "unidade": "m2"}])
    assert {c.regra for c in m2} == {"pintura"}
    assert _por_desc(m2, "Selador")[0].quantidade == 2
    assert _por_desc(m2, "Massa corrida")[0].quantidade == 4
    assert _por_desc(m2, "Fita crepe")[0].quantidade == 12
    litros = sugerir_complementos([{"linha": 1, "descricao": "Tinta látex", "quantidade": 36,
                                    "unidade": "L"}])  # 36 L ≈ 180 m²
    assert _por_desc(litros, "Selador")[0].quantidade == 2


def test_vaso_sanitario_por_unidade():
    res = sugerir_complementos([{"linha": 7, "descricao": "Vaso sanitário Deca Link", "quantidade": 2,
                                 "unidade": "un"}])
    assert {c.descricao for c in res} >= {"Assento sanitário", "Anel de vedação para vaso"}
    assert _por_desc(res, "Assento")[0].quantidade == 2


def test_vaso_com_caixa_acoplada_continua_sendo_vaso():
    res = sugerir_complementos([{"linha": 1, "descricao": "Vaso sanitario com caixa acoplada",
                                 "quantidade": 2, "unidade": "un"}])
    assert _por_desc(res, "Assento")[0].quantidade == 2


def test_caixa_acoplada_avulsa_nao_conta_como_vaso():
    res = sugerir_complementos([{"linha": 1, "descricao": "Caixa acoplada para vaso sanitario",
                                 "quantidade": 2, "unidade": "un"}])
    assert res == []


def test_drywall():
    res = sugerir_complementos([{"linha": 1, "descricao": "Placa de drywall ST 12,5 mm",
                                 "quantidade": 100, "unidade": "m2"}])
    assert _por_desc(res, "Perfil")[0].quantidade == 80
    assert _por_desc(res, "Parafuso")[0].quantidade == 2


def test_fita_crepe_da_pintura_nao_suprime_fita_do_drywall():
    itens = [
        {"linha": 1, "descricao": "Placa de drywall", "quantidade": 20, "unidade": "m2"},
        {"linha": 2, "descricao": "Fita crepe 48 mm", "quantidade": 4, "unidade": "un"},
    ]
    assert _por_desc(sugerir_complementos(itens), "Fita telada")


def test_entradas_invalidas_nao_quebram():
    itens = [
        {"linha": 1, "descricao": "Porcelanato", "quantidade": None, "unidade": "m2"},
        {"linha": 2, "descricao": None, "quantidade": "abc", "unidade": None},
        {"linha": 3, "descricao": "Porcelanato", "quantidade": -5, "unidade": "m2"},
        {},
    ]
    assert sugerir_complementos(itens) == []
    assert sugerir_complementos([]) == []


def test_obra_real_cozinha_graças():
    d = json.loads((ROOT / "docs/arquivos-teste/03-cozinha-gracas/orcamento_cozinha-gracas.json")
                   .read_text(encoding="utf-8"))
    itens = [{"linha": i + 1, **it} for i, it in enumerate(d["itens"])]
    res = sugerir_complementos(itens)
    assert all(c.quantidade > 0 and c.motivo for c in res)
    print([(c.descricao, c.quantidade) for c in res])


def test_categoria_com_argamassa_nao_desativa_a_regra_nem_conta_como_ja_tem():
    # categoria real dos arquivos de teste: "Revestimentos e argamassas"
    itens = [{"linha": 4, "categoria": "Revestimentos e argamassas", "descricao": "Portinari metrô branco",
              "quantidade": 14, "unidade": "m2"}]
    res = sugerir_complementos(itens)
    assert _por_desc(res, "AC-III")[0].quantidade == 5      # 14 m² * 6 kg / 20 kg
    assert _por_desc(res, "Rejunte")


def test_item_de_argamassa_na_categoria_nao_aciona_a_regra_de_piso():
    itens = [{"linha": 1, "categoria": "Revestimentos e argamassas", "descricao": "Argamassa AC-III 20 kg",
              "quantidade": 10, "unidade": "un"},
             {"linha": 2, "categoria": "Revestimentos e argamassas", "descricao": "Rejunte Quartzolit",
              "quantidade": 4, "unidade": "un"}]
    assert sugerir_complementos(itens) == []


def test_categoria_pintura_aciona_mesmo_sem_a_palavra_tinta_na_descricao():
    res = sugerir_complementos([{"linha": 1, "categoria": "Pintura", "descricao": "Coral Decora cinza urbano",
                                 "quantidade": 22, "unidade": "m2"}])
    assert {c.regra for c in res} == {"pintura"}


def test_argamassa_pela_marca_nao_e_piso_nem_falta():
    """Caso real da Casa térrea (site, 07/11): 'Votomassa AC-II' na categoria 'Revestimentos e argamassas' entrava
    na área de piso (324 m² em vez de 162) e a regra sugeria 98 sacos de argamassa para uma lista que já tinha."""
    from src.complementos import sugerir_complementos
    cat = "Revestimentos e argamassas"
    itens = [{"linha": 7, "categoria": cat, "descricao": "Eliane Munari 60x60", "quantidade": 120, "unidade": "m2"},
             {"linha": 8, "categoria": cat, "descricao": "Votomassa AC-II", "quantidade": 162, "unidade": "m2"},
             {"linha": 9, "categoria": cat, "descricao": "Rejunte Quartzolit cinza platina", "quantidade": 120, "unidade": "m2"},
             {"linha": 10, "categoria": cat, "descricao": "Ceusa branco 30x60", "quantidade": 42, "unidade": "m2"}]
    sug = sugerir_complementos(itens)
    assert [s.descricao for s in sug] == ["Espaçador/nivelador de piso (pacote 100 un)"]
    assert sug[0].origem_linhas == [7, 10] and "162 m²" in sug[0].motivo


def test_rejunte_acrilico_nao_vira_pintura():
    from src.complementos import sugerir_complementos
    sug = sugerir_complementos([{"linha": 1, "categoria": "Piscina", "descricao": "Rejunte acrílico cinza",
                                 "quantidade": 30, "unidade": "m2"}])
    assert not [s for s in sug if s.regra == "pintura"]
