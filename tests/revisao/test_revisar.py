import copy

import pytest

from src.revisao import revisar_itens
from tests.revisao.conftest import item


def por_regra(erros, regra):
    return [e for e in erros if e.regra == regra]


def linhas_removidas(erros):
    return sorted(r.linha for e in por_regra(erros, "duplicado") if e.correcao for r in e.correcao.remover)


def erros_de_unidade_por_descricao(itens):
    por_linha = {e.linhas[0]: e for e in revisar_itens(itens) if e.regra == "unidade"}
    return {i["descricao"]: por_linha[i["linhaOrigem"]] for i in itens if i["linhaOrigem"] in por_linha}


# ------------------------------------------------------------------ propriedades gerais

def test_nao_altera_a_lista_original():
    itens = [item("Guia 48 Knauf", 40, "m2", linha=3), item("Tomada Liz 10A", 30000, "un", linha=4)]
    antes = copy.deepcopy(itens)
    assert revisar_itens(itens)
    assert itens == antes


def test_ids_estaveis_e_deterministicos():
    itens = [item("Cimento Votoran", 180, "sc", linha=2, id="a")]
    assert [e.id for e in revisar_itens(itens)] == [e.id for e in revisar_itens(copy.deepcopy(itens))]


def test_lista_limpa_nao_gera_erro():
    itens = [item("Tomada Liz 10A", 30, "un"), item("Cabo SIL 2,5 azul", 600, "m"),
             item("Porcelanato Portobello 90x90", 48, "m²"), item("Tinta branca", 180, "m2")]
    assert revisar_itens(itens) == []


def test_erro_traz_campos_do_contrato():
    (e,) = revisar_itens([item("Cimento Votoran", 180, "sc", linha=16, id="x1")])
    assert e.regra == "unidade" and e.linhas == [16] and e.item_ids == ["x1"] and e.campo == "unidade"
    assert e.valor_atual == "sc" and e.motivo and e.id
    assert e.correcao.acao == "alterar"
    (alt,) = e.correcao.alteracoes
    assert (alt.linha, alt.campo, alt.de, alt.para) == (16, "unidade", "sc", "un")


# ------------------------------------------------------------------ unidade

def test_unidades_fora_da_lista_da_casa_terrea(carregar):
    itens = carregar("02-casa-terrea-aldeia", "lista_materiais_casa-terrea-aldeia.csv")
    erros = revisar_itens(itens)
    un = por_regra(erros, "unidade")
    assert {(e.valor_atual, e.fatos["significado"]) for e in un} == {("sc", "saco"), ("br", "barra")}
    assert len(un) == 4  # cimento, cal, ferro 3/8, ferro 5 mm
    assert all(e.correcao.alteracoes[0].para == "un" for e in un)
    # falso positivo: o arquivo não tem duplicados nem colunas trocadas
    assert not por_regra(erros, "duplicado") and not por_regra(erros, "colunas_trocadas")


def test_unidade_incompativel_com_o_produto(carregar):
    itens = carregar("07-clinica-derby", "quantidades_unidades_bagunçadas.csv")
    por_desc = erros_de_unidade_por_descricao(itens)
    assert por_desc["Guia 48 Knauf"].correcao.alteracoes[0].para == "m"       # perfil em m², vira m
    assert por_desc["Celite Azalea"].correcao.alteracoes[0].para == "un"      # vaso em m²
    assert por_desc["Tomada Liz 10A"].correcao.alteracoes[0].para == "un"
    assert por_desc["Suvinil T. Seda branco neve"].correcao.alteracoes[0].para == "m2"  # tinta em m
    # falso positivo: tinta em m2, placa em un e montante em "pç" (un) passam
    for ok in ("Fundo preparador Suvinil", "Coral Rende Muito branco", "Placa RU Placo", "Montante 48 Knauf"):
        assert ok not in por_desc


def test_unidade_ausente_propoe_a_da_familia(carregar):
    itens = carregar("01-apto-boa-viagem", "lista_materiais_INCOMPLETA.csv")
    por_desc = erros_de_unidade_por_descricao(itens)
    assert por_desc["Ceusa branco 30x60"].correcao.alteracoes[0].para == "m2"
    assert por_desc["Rodapé Santa Luzia 10 cm"].correcao.alteracoes[0].para == "m"
    assert por_desc["Cabo SIL 2,5 azul"].fatos["inferida_da_familia"] is True
    # sem pista do produto não há erro; unidade preenchida com quantidade "verificar" não é erro de unidade
    assert "Hydra Max" not in por_desc
    assert "Biancogres calacata 60x120" not in por_desc


def test_unidade_desconhecida_sem_proposta():
    (e,) = revisar_itens([item("Selador Coral", 3, "xyz")])
    assert e.correcao is None and e.fatos["subtipo"] == "desconhecida"
    assert "Sem proposta automática" in e.texto


def test_grafia_da_unidade():
    (e,) = revisar_itens([item("Cabo SIL 2,5 azul", 100, "mts")])
    assert e.fatos["subtipo"] == "grafia" and e.correcao.alteracoes[0].para == "m"


@pytest.mark.parametrize("un", ["m²", "m2"])
def test_grafias_aceitas_nao_geram_erro(un):
    assert revisar_itens([item("Tinta Suvinil branca", 100, un)]) == []


def test_unidade_numerica_com_quantidade_numerica_nao_e_troca():
    erros = revisar_itens([item("Selador Coral", 10, "5")])
    assert not por_regra(erros, "colunas_trocadas")
    assert por_regra(erros, "unidade")[0].correcao is None


# ------------------------------------------------------------------ quantidade

def test_quantidade_desproporcional_com_correcao_de_milhar():
    (e,) = revisar_itens([item("Tomada Liz 10A", 30000, "un", linha=7)])
    assert e.regra == "quantidade" and e.fatos["lado"] == "acima" and e.fatos["fator"] == 1000
    assert e.correcao.alteracoes[0].para == "30"


def test_quantidade_fora_da_faixa_sem_correcao_segura():
    (e,) = revisar_itens([item("Porta pronta Pormade 80", 1234, "un")])
    assert e.correcao is None


def test_quantidade_normal_nao_gera_erro(carregar):
    # falsos positivos: 3.000 parafusos, 9.500 tijolos, 800 m de cabo e 48 painéis são plausíveis
    for pasta, arq in [("06-escritorio-ilha-do-leite", "lista_com_duplicados.csv"),
                       ("02-casa-terrea-aldeia", "lista_materiais_casa-terrea-aldeia.csv")]:
        assert not por_regra(revisar_itens(carregar(pasta, arq)), "quantidade")


def test_rejunte_alem_da_area_de_revestimento():
    itens = [item("Porcelanato Portobello 90x90", 10, "m2", linha=1), item("Rejunte Quartzolit cinza", 500, "m2", linha=2)]
    (e,) = revisar_itens(itens)
    assert e.regra == "quantidade" and e.linhas == [2] and e.correcao is None


def test_rejunte_sem_referencia_ou_dentro_do_limite_nao_gera_erro():
    assert revisar_itens([item("Rejunte Quartzolit cinza", 500, "m2")]) == []
    itens = [item("Porcelanato Portobello 90x90", 10, "m2"), item("Rejunte Quartzolit cinza", 12, "m2")]
    assert revisar_itens(itens) == []


# ------------------------------------------------------------------ duplicados

def test_duplicados_com_nomes_distintos(carregar):
    itens = carregar("06-escritorio-ilha-do-leite", "lista_com_duplicados.csv")
    erros = revisar_itens(itens)
    nomes = {i["linhaOrigem"]: i["descricao"] for i in itens}
    removidas = {nomes[n] for n in linhas_removidas(erros)}
    assert removidas == {
        "Tinta acrílica acetinada branca", "Porcelanato marmorizado branco polido 60x120",
        "Lã de vidro 50 mm para isolamento acústico", "Massa para juntas de drywall",
        "Vaso sanitário com caixa acoplada linha econômica", "Luminária painel LED 60x60",
        "Disjuntor monopolar 20 A", "Porta de madeira pronta 80x210 branca", "Ar-condicionado split 9.000 BTUs",
    }
    for e in por_regra(erros, "duplicado"):
        assert len(e.linhas) == 2 and e.correcao.acao == "remover"
    assert not por_regra(erros, "quantidade") and not por_regra(erros, "colunas_trocadas")


def test_duas_marcas_definidas_nao_sao_duplicata():
    assert revisar_itens([item("Torneira Docol bica alta", 4, "un"), item("Cuba de apoio Deca", 4, "un")]) == []
    assert revisar_itens([item("Disjuntor Easy9 1P 20A", 24, "un"), item("Disjuntor Steck 20A", 24, "un")]) == []


def test_cor_diferente_nao_e_duplicata():
    assert revisar_itens([item("Cabo SIL 2,5 azul", 300, "m"), item("Cabo elétrico 2,5 verde", 300, "m")]) == []


def test_medida_diferente_nao_e_duplicata():
    assert revisar_itens([item("Porcelanato Portobello 90x90", 48, "m2"), item("Porcelanato cinza 60x60", 48, "m2")]) == []


def test_acabamento_diferente_nao_e_duplicata():
    assert revisar_itens([item("Suvinil Toque de Seda branco", 58, "m2"), item("Tinta acrílica fosca branca", 58, "m2")]) == []


def test_quantidade_ou_unidade_diferente_nao_e_duplicata():
    assert revisar_itens([item("Suvinil T. Seda branco neve", 520, "m2"), item("Tinta acrílica acetinada branca", 400, "m2")]) == []
    assert revisar_itens([item("Suvinil T. Seda branco neve", 520, "m2"), item("Tinta acrílica acetinada branca", 520, "l")]) == []


def test_mesmo_nome_vira_mesclagem_com_soma():
    itens = [item("Selador Coral", 100, "m2", linha=2, id="a"), item("selador coral", "80", "m²", linha=5, id="b")]
    (e,) = revisar_itens(itens)
    assert e.correcao.acao == "mesclar"
    assert e.correcao.alteracoes[0].para == "180" and [r.linha for r in e.correcao.remover] == [5]


def test_mesmo_nome_em_niveis_diferentes_nao_e_duplicata():
    itens = [item("Selador Coral", 100, "m2", nivel="Térreo"), item("Selador Coral", 80, "m2", nivel="Superior")]
    assert revisar_itens(itens) == []


def test_mesmo_nome_com_unidades_diferentes_nao_e_duplicata():
    assert revisar_itens([item("Selador Coral", 10, "m2"), item("Selador Coral", 10, "l")]) == []


def test_generico_ambiguo_fica_sem_proposta():
    itens = [item("Tinta Suvinil branca", 50, "m2", linha=1), item("Tinta Coral branca", 50, "m2", linha=2),
             item("Tinta acrílica branca", 50, "m2", linha=3)]
    (e,) = revisar_itens(itens)
    assert e.correcao is None and e.fatos["candidatos_a_manter"] == [1, 2]


# ------------------------------------------------------------------ colunas trocadas

def test_colunas_trocadas_do_acervo(carregar):
    itens = carregar("04-banheiro-casa-forte", "lista_colunas_trocadas.csv")
    (e,) = revisar_itens(itens)
    assert e.regra == "colunas_trocadas" and len(e.linhas) == len(itens) == 26
    alts = {(a.linha, a.campo): a.para for a in e.correcao.alteracoes}
    assert alts[(2, "quantidade")] == "4,20" and alts[(4, "quantidade")] == "22"
    assert alts[(2, "unidade")] == "m2"      # inferida da família: a importação perdeu o "m²" da coluna Quantidade
    assert alts[(14, "unidade")] == "un"     # vaso sanitário


def test_colunas_trocadas_no_formato_bruto():
    itens = [item("Coral Rende Muito branco", "m²", "4,20", linha=2), item("Roca Debba suspensa", "un", "1", linha=3)]
    (e,) = revisar_itens(itens)
    alts = {(a.linha, a.campo): a.para for a in e.correcao.alteracoes}
    assert alts == {(2, "quantidade"): "4,20", (2, "unidade"): "m2", (3, "quantidade"): "1", (3, "unidade"): "un"}


def test_listas_normais_nao_tem_colunas_trocadas(carregar):
    for pasta, arq in [("01-apto-boa-viagem", "lista_materiais_INCOMPLETA.csv"),
                       ("02-casa-terrea-aldeia", "lista_materiais_casa-terrea-aldeia.csv"),
                       ("06-escritorio-ilha-do-leite", "lista_com_duplicados.csv")]:
        assert not por_regra(revisar_itens(carregar(pasta, arq)), "colunas_trocadas")


def test_linha_sem_quantidade_e_unidade_valida_nao_e_troca():
    assert not por_regra(revisar_itens([item("Selador Coral", "", "m2")]), "colunas_trocadas")
