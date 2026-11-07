"""Etapa 3 — extrair preço e conferir se é o mesmo produto (modelo rápido + trava anti-alucinação)."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import APIStatusError

import src.precos as p
from src.busca import ResultadoWeb, buscar, montar_consulta
from src.modelos import ItemEntrada

ANUNCIOS = [
    ResultadoWeb("Tinta Toque de Seda Suvinil 18L", "https://www.telhanorte.com.br/a", "telhanorte.com.br", "Telhanorte",
                 "Ref: 2533111 R$ 739,90 Pix R$ 702,90"),
    ResultadoWeb("Tinta Suvinil Toque de Seda 18l Branco Neve", "https://www.magazineluiza.com.br/b", "magazineluiza.com.br",
                 "Magazine Luiza", "5.0 (4) R$ 849,00 ou 10x de R$ 84,90 sem juros"),
    ResultadoWeb("Tinta Suvinil Toque De Seda 3,6L", "https://www.mercadolivre.com.br/c", "mercadolivre.com.br",
                 "Mercado Livre", "R$ 189 em 12x R$ 15,75 Frete grátis"),
    ResultadoWeb("Kit 2 latas Suvinil Toque de Seda 18L", "https://www.amazon.com.br/d", "amazon.com.br", "Amazon",
                 "R$ 1.599,00 Frete R$ 45,00"),
]
PRODUTO = "Tinta acrílica acetinada Suvinil Toque de Seda Branco Neve 18L"


# ---------------------------------------------------------------- offline: trava anti-alucinação
@pytest.mark.parametrize("preco,texto,esperado", [
    (739.9, "R$ 739,90 Pix", True), (849.0, "R$ 849,00 ou 10x", True), (189.0, "R$ 189 em 12x", True),
    (1599.0, "R$ 1.599,00 Frete", True), (1599.0, "R$1599,00", True),
    (750.0, "R$ 739,90", False),          # inventado
    (39.9, "R$ 739,90", False),           # pedaço de outro número não conta
    (84.9, "10x de R$ 84,90", True),      # a trava só garante que existe no texto; parcela é papel do prompt
])
def test_preco_precisa_estar_escrito_no_anuncio(preco, texto, esperado):
    assert p.preco_no_texto(preco, texto) is esperado


# ---------------------------------------------------------------- offline: leitura da resposta
def test_le_linhas_e_mapeia_s_p_n():
    resp = "<think>\n</think>\n0|739.90|lata 18 L|S\n1|849.00|lata 18 L|S\n2|189.00|galão 3,6 L|P\n3|1599.00|kit 2 latas 18 L|P"
    ofertas, alucinadas = p.ler_resposta(resp, ANUNCIOS)
    assert [(o.loja, o.preco, o.mesmo_produto) for o in ofertas] == [
        ("Telhanorte", 739.9, "sim"), ("Magazine Luiza", 849.0, "sim"), ("Mercado Livre", 189.0, "parecido"),
        ("Amazon", 1599.0, "parecido")]
    assert alucinadas == 0


def test_descarta_preco_inventado_e_lixo():
    resp = "Aqui está:\n0|750.00|lata 18 L|S\n9|10.00|x|S\nlinha solta\n1|849.00|lata 18 L|S\n1|1.00|repetido|S"
    ofertas, alucinadas = p.ler_resposta(resp, ANUNCIOS)
    assert alucinadas == 1
    assert [(o.loja, o.preco) for o in ofertas] == [("Telhanorte", None), ("Magazine Luiza", 849.0)]


def test_valor_desconhecido_rejeita_a_linha_em_vez_de_virar_nao():
    """Regressão (revisão da etapa 3): os modelos copiavam o nome do campo 'M' em vez de S/P/N, e o
    leitor antigo transformava isso em 'outro produto' calado — toda tinta certa era descartada."""
    ofertas, _ = p.ler_resposta("0|739.90|lata 18 L|M\n1|849.00|lata 18 L|SIM\n2|189.00|galão 3,6 L|PARECIDO", ANUNCIOS)
    assert [(o.loja, o.mesmo_produto) for o in ofertas] == [("Magazine Luiza", "sim"), ("Mercado Livre", "parecido")]


def test_aceita_palavras_inteiras_e_variacoes():
    resp = "0|739.90|lata 18 L|SIM\n1|849.00|lata 18 L|sim.\n2|189.00|galão|Parecido\n3|1599.00|kit|NÃO"
    ofertas, _ = p.ler_resposta(resp, ANUNCIOS)
    assert [o.mesmo_produto for o in ofertas] == ["sim", "sim", "parecido", "nao"]


def test_conferidas_so_mesmo_produto_com_preco():
    ofertas, _ = p.ler_resposta("0|739.90|lata 18 L|S\n1|-|-|S\n2|189.00|galão|P", ANUNCIOS)
    r = p.ResultadoExtracao(ofertas=ofertas)
    assert [o.loja for o in r.conferidas] == ["Telhanorte"]
    assert r.conferidas[0].para_fonte().preco_embalagem == 739.9


# ---------------------------------------------------------------- offline: reserva
VAZIA = object()


class _ClienteFalso:
    def __init__(self, roteiro): self.roteiro, self.modelos = roteiro, []
    @property
    def chat(self): return NS(completions=NS(create=self._create))
    async def _create(self, model, **kw):
        self.modelos.append(model)
        acao = self.roteiro[len(self.modelos) - 1]
        if isinstance(acao, Exception):
            raise acao
        if acao is VAZIA:   # Featherless sobrecarregada: HTTP 200 sem choices
            return NS(choices=None, usage=None, error={"type": "server_error", "code": "failed_generation"})
        return NS(choices=[NS(message=NS(content=acao))], usage=NS(prompt_tokens=100, completion_tokens=20, cost=0.0001))


def _http(status):
    return APIStatusError("x", response=httpx.Response(status, request=httpx.Request("POST", "http://x")), body=None)


@pytest.mark.parametrize("primeira", [_http(503), "não sei"])
def test_usa_reserva_se_principal_falha_ou_responde_lixo(primeira):
    cli = _ClienteFalso([primeira, "0|739.90|lata 18 L|S"])
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    assert cli.modelos == ["Qwen/Qwen3-32B", p.MODELO_RESERVA_EXTRACAO]
    assert r.modelo == p.MODELO_RESERVA_EXTRACAO and r.conferidas and r.erro is None


def test_resposta_vazia_da_featherless_tenta_de_novo_no_mesmo_modelo(monkeypatch):
    """Regressão (aquecimento da etapa 9): 200 sem `choices` virava TypeError e ia direto para a reserva."""
    monkeypatch.setattr(p.asyncio, "sleep", _sem_espera)
    cli = _ClienteFalso([VAZIA, "0|739.90|lata 18 L|S"])
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    assert cli.modelos == ["Qwen/Qwen3-32B", "Qwen/Qwen3-32B"] and r.modelo == "Qwen/Qwen3-32B" and r.conferidas


def test_duas_respostas_vazias_vao_para_a_reserva(monkeypatch):
    monkeypatch.setattr(p.asyncio, "sleep", _sem_espera)
    cli = _ClienteFalso([VAZIA, VAZIA, "0|739.90|lata 18 L|S"])
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    assert r.modelo == p.MODELO_RESERVA_EXTRACAO and "RespostaVazia" in r.tentativas[0]


async def _sem_espera(_):
    return None


def test_modelo_fora_do_ar_e_pulado_nas_proximas_extracoes(monkeypatch):
    """Achado real (07/11 14h): 'Qwen/Qwen3-32B is not available for inference' (HTTP 400). Sem o disjuntor,
    cada extração perdia até 19 s nessa chamada antes da reserva e o agente estourava os 40 s."""
    monkeypatch.setattr(p, "_indisponivel_ate", {})
    cli = _ClienteFalso([_http(400), "0|739.90|lata 18 L|S", "0|739.90|lata 18 L|S"])
    asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    assert cli.modelos == ["Qwen/Qwen3-32B", p.MODELO_RESERVA_EXTRACAO, p.MODELO_RESERVA_EXTRACAO]
    assert r.modelo == p.MODELO_RESERVA_EXTRACAO and r.conferidas


def test_503_nao_desliga_o_modelo_e_disjuntor_volta_depois_da_pausa(monkeypatch):
    monkeypatch.setattr(p, "_indisponivel_ate", {})
    cli = _ClienteFalso([_http(503), "0|739.90|lata 18 L|S", "0|739.90|lata 18 L|S"])
    asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS, cliente=cli))
    assert cli.modelos[2] == "Qwen/Qwen3-32B", "503 é passageiro: o principal continua sendo tentado"
    p._marcar_indisponivel("Qwen/Qwen3-32B")
    p._indisponivel_ate["Qwen/Qwen3-32B"] = 0   # pausa acabou
    assert p.modelos_extracao()[0] == "Qwen/Qwen3-32B"
    p._marcar_indisponivel("Qwen/Qwen3-32B"); p._marcar_indisponivel(p.MODELO_RESERVA_EXTRACAO)
    assert p.modelos_extracao() == ["Qwen/Qwen3-32B", p.MODELO_RESERVA_EXTRACAO], "todos fora: tenta todos"


def test_sem_anuncios_nao_chama_llm():
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, [], cliente=_ClienteFalso([])))
    assert r.erro and not r.ofertas


# ---------------------------------------------------------------- real (Featherless; Tavily no último)
@pytest.mark.real
def test_etapa3_extracao_real_acerta_o_caso_de_controle():
    """Caso montado com resposta conhecida: 2 iguais, 1 tamanho diferente, 1 kit."""
    t0 = time.perf_counter()
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, ANUNCIOS))
    dur = time.perf_counter() - t0
    got = {o.loja: (o.preco, o.mesmo_produto) for o in r.ofertas}
    assert got.get("Telhanorte") == (739.9, "sim") and got.get("Magazine Luiza") == (849.0, "sim"), got
    assert got.get("Mercado Livre", (None, "?"))[1] != "sim" and got.get("Amazon", (None, "?"))[1] != "sim", got
    assert r.descartadas_alucinacao == 0
    assert dur < 15, f"extração lenta: {dur:.1f}s"


@pytest.mark.real
def test_etapa3_ponta_a_ponta_busca_mais_extracao():
    busca = asyncio.run(buscar(montar_consulta(ItemEntrada(id="1", descricao=PRODUTO))))
    r = asyncio.run(p.extrair_e_conferir(PRODUTO, busca.resultados))
    assert r.ofertas, r.erro
    assert all(p.preco_no_texto(o.preco, f"{o.titulo} {next(x.trecho for x in busca.resultados if x.url == o.url)}")
               for o in r.ofertas if o.preco), "nenhum preço pode estar fora do texto"
