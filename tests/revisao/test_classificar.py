import pytest

from src.revisao import classificar_item, marcas_encontradas

DEFINIDOS = [
    "Suvinil Toque de Seda Branco Neve 18L",   # marca + linha
    "Tomada Liz 10A",                          # só modelo (Liz, da Legrand)
    "Cimento Votoran",
    "Coral Rende Muito branco",
    "Quartzolit AC-III",
    "Porcelanato Portobello cimento 90x90",
    "suvinil",                                 # marca sozinha basta
]
PENDENTES = [
    "tinta branca",
    "Tinta acrílica acetinada branca",
    "Porcelanato 90x90 acetinado",
    "Areia média",
    "Tijolo 14x19x29",
    "Vaso sanitário com caixa acoplada linha econômica",
    "Tinta cor coral",                          # falso positivo: "coral" é cor, não a marca
    "Tinta salmão tom coral para sala",
    "Calçada de pedra",                         # marcas curtas só valem como palavra inteira
    "Alizar de madeira",
    "",
    None,
]


@pytest.mark.parametrize("d", DEFINIDOS)
def test_definido(d):
    assert classificar_item(d) == "definido"


@pytest.mark.parametrize("d", PENDENTES)
def test_pendente(d):
    assert classificar_item(d) == "pendente"


def test_acento_e_caixa_nao_importam():
    assert classificar_item("PORTÃO CORAL SUVINIL") == "definido"
    assert classificar_item("Rodapé SÃO GABRIEL") == "definido"


def test_marcas_para_auditoria():
    assert marcas_encontradas("Massa corrida Suvinil") == ["suvinil"]


def test_acervo_casa_terrea(carregar):
    itens = carregar("02-casa-terrea-aldeia", "lista_materiais_casa-terrea-aldeia.csv")
    cls = {i["descricao"]: classificar_item(i["descricao"]) for i in itens}
    for generico in ("Areia média", "Brita 1", "Tijolo 14x19x29", "Grama esmeralda"):
        assert cls[generico] == "pendente", generico
    for definido in ("Selador Coral", "Cimento Votoran", "Tela Q-92 Gerdau", "Concreto Supermix fck25"):
        assert cls[definido] == "definido", definido
