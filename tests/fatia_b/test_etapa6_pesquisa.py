"""Etapa 6 — orquestração por item: cache → busca → extração → agente refaz → cálculo → resultado.
Offline: busca, extração, cache e LLM do agente são trocados por roteiros (dublês)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

import src.pesquisa as p
from src.busca import RespostaBusca
from src.cache import EntradaCache
from src.modelos import ItemEntrada
from src.precos import Oferta, ResultadoExtracao

TINTA = ItemEntrada(id="1", descricao="Tinta Suvinil Toque de Seda Branco Neve 18L", quantidade=180, unidade="m2")
MISTURADOR = ItemEntrada(id="2", descricao="Misturador monocomando Deca Link para cozinha", quantidade=1, unidade="un")


def of(loja, preco, emb="lata 18 L", igual="sim", titulo=None):
    return Oferta(loja=loja, dominio=f"{loja.lower().replace(' ', '')}.com.br", url=f"https://{loja}/{preco}/{igual}",
                  titulo=titulo or loja, preco=preco, embalagem=emb, mesmo_produto=igual)


# ---------------------------------------------------------------- dublês
class Mundo:
    """Roteiro de buscas por consulta + cache em memória."""

    def __init__(self, buscas: dict[str, list[Oferta]], cache_linha: EntradaCache | None = None, padrao=None):
        self.buscas, self.cache_linha, self.padrao = buscas, cache_linha, padrao or []
        self.consultas: list[str] = []
        self.gravados: list = []

    async def buscar_e_extrair(self, consulta, produto):
        self.consultas.append(consulta)
        ofertas = next((v for k, v in self.buscas.items() if k in consulta.lower()), self.padrao)
        return (RespostaBusca(consulta, "tavily", imagem=f"https://img/{len(self.consultas)}.jpg",
                              erro=None if ofertas else "nenhuma loja da lista retornou resultado"),
                ResultadoExtracao(ofertas=list(ofertas), modelo="Qwen/Qwen3-32B"))

    async def ler(self, descricao, aceitar_vencido=False, cliente=None):
        e = self.cache_linha
        return e if e and (aceitar_vencido or not e.vencido) else None

    async def gravar(self, descricao, extracao, imagem_url, provedor=None, anterior=None, cliente=None, iteracoes=0):
        self.gravados.append((descricao, len(extracao.ofertas), imagem_url))
        self.iteracoes_gravadas = iteracoes
        return True


@pytest.fixture
def mundo(monkeypatch):
    def montar(buscas, cache_linha=None, padrao=None):
        m = Mundo(buscas, cache_linha, padrao)
        monkeypatch.setattr(p, "buscar_e_extrair", m.buscar_e_extrair)
        monkeypatch.setattr(p.cache, "ler", m.ler)
        monkeypatch.setattr(p.cache, "gravar", m.gravar)
        return m
    return montar


class _Msg:
    def __init__(self, content=None, tool_calls=None): self.content, self.tool_calls = content, tool_calls
    def model_dump(self, exclude_none=True):
        d = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name, "arguments": c.function.arguments}}
                               for c in self.tool_calls]
        return d


class LLMFalso:
    """Imita o cliente OpenAI síncrono: cada item do roteiro é ('buscar', consulta) ou ('fim', texto)."""

    def __init__(self, roteiro): self.roteiro, self.chamadas = list(roteiro), 0
    @property
    def chat(self): return NS(completions=NS(create=self._create))

    def _create(self, model, messages, tools=None, temperature=None, top_p=None):
        acao, valor = self.roteiro[self.chamadas]
        self.chamadas += 1
        if acao == "buscar":
            msg = _Msg("A busca trouxe outra linha; vou incluir o modelo.",
                       [NS(id=f"c{self.chamadas}", function=NS(name="buscar_preco", arguments=json.dumps({"consulta": valor})))])
        else:
            msg = _Msg(valor)
        return NS(choices=[NS(message=msg)], model=model, usage=NS(prompt_tokens=10, completion_tokens=5, cost=0.0001))


def rodar(item, **kw):
    return asyncio.run(p.pesquisar_item(item, **kw))


# ---------------------------------------------------------------- caminho fixo
def test_cache_valido_responde_sem_buscar(mundo):
    entrada = EntradaCache(chave="x", descricao=TINTA.descricao, imagem_url="https://img.example/cache.jpg", provedor="tavily",
                           extracao=ResultadoExtracao(ofertas=[of("Telhanorte", 739.9), of("Magazine Luiza", 849.0)]),
                           atualizado_em=datetime.now(timezone.utc) - timedelta(days=1), vencido=False)
    m = mundo({}, cache_linha=entrada)
    r = rodar(TINTA, cliente_llm=LLMFalso([]))
    assert r.status == "definido" and r.imagem_url == "https://img.example/cache.jpg" and r.qtd_embalagens == 2
    assert m.consultas == [] and r.iteracoes == 0 and r.premissa.startswith("rendimento")


def test_achou_lojas_suficientes_nao_chama_agente(mundo):
    m = mundo({}, padrao=[of("Telhanorte", 739.9), of("Magazine Luiza", 849.0), of("Sertão", 749.9)])
    llm = LLMFalso([])
    r = rodar(TINTA, cliente_llm=llm)
    assert r.status == "definido" and len(r.fontes) == 3 and r.confianca == "alta"
    assert llm.chamadas == 0 and r.iteracoes == 0 and len(m.gravados) == 1


# ---------------------------------------------------------------- agente
def test_agente_reformula_e_acha_mais_lojas(mundo):
    """Caso real da avaliação: misturador Deca com 1 loja só → o agente refaz com o nome da linha."""
    m = mundo({"link 1875": [of("Leroy Merlin", 1799.0, "unidade"), of("Loja Dexco", 1850.0, "unidade")]},
              padrao=[of("Magazine Luiza", 1878.78, "unidade"), of("Leroy Merlin", 990.5, "unidade", "parecido", "Misturador Deca Polo")])
    llm = LLMFalso([("buscar", "misturador Deca Link 1875 cozinha"), ("fim", "FIM: incluí a referência do modelo")])
    r = rodar(MISTURADOR, cliente_llm=llm)
    assert r.status == "definido" and r.iteracoes == 1
    assert {f.loja for f in r.fontes} == {"Magazine Luiza", "Leroy Merlin", "Loja Dexco"}
    assert m.consultas[1] == "misturador Deca Link 1875 cozinha"
    assert llm.chamadas == 1, "com 2+ lojas o código encerra sem gastar outra chamada ao LLM só para ouvir FIM"


def test_agente_nao_passa_do_limite_de_buscas(mundo):
    mundo({}, padrao=[of("Magazine Luiza", 1878.78, "unidade")])
    llm = LLMFalso([("buscar", "deca link a"), ("buscar", "deca link b"), ("buscar", "deca link c"), ("fim", "FIM: desisti")])
    r = rodar(MISTURADOR, cliente_llm=llm)
    assert r.iteracoes == 2, "no máximo 2 buscas extras por item"
    assert r.status == "definido" and r.confianca == "baixa"   # 1 loja: tem preço, mas a tela mostra a confiança


def test_so_parecidos_vira_estimativa_com_pergunta(mundo):
    mundo({}, padrao=[of("Leroy Merlin", 990.5, "unidade", "parecido"), of("Loja Dexco", 1625.9, "unidade", "parecido")])
    r = rodar(MISTURADOR, cliente_llm=LLMFalso([("fim", "FIM: nada novo")]))
    assert r.status == "pendente_especificacao" and r.estimativa and "modelo" in r.pergunta
    assert r.preco_emb_med and r.motivo


# ---------------------------------------------------------------- genérico, falhas
def test_generico_pergunta_ao_arquiteto_sem_agente(mundo):
    mundo({}, padrao=[of("Loja Suvinil", 290.9, "galão 3,6 L", "parecido"), of("Leroy Merlin", 89.9, "6 L", "parecido")])
    llm = LLMFalso([])
    item = ItemEntrada(id="3", descricao="Tinta acrílica fosca vermelha", quantidade=12, unidade="m2",
                       classificacao="pendente_especificacao")
    r = rodar(item, cliente_llm=llm)
    assert r.status == "pendente_especificacao" and r.estimativa and "acabamento" in r.pergunta
    assert llm.chamadas == 0


def test_falha_total_usa_cache_vencido_com_a_data(mundo):
    vencido = EntradaCache(chave="x", descricao=TINTA.descricao, imagem_url="https://img/velha.jpg", provedor="tavily",
                           extracao=ResultadoExtracao(ofertas=[of("Telhanorte", 699.9), of("Sertão", 719.9)]),
                           atualizado_em=datetime(2026, 10, 20, 15, tzinfo=timezone.utc), vencido=True)
    mundo({}, cache_linha=vencido)
    r = rodar(TINTA, cliente_llm=LLMFalso([("fim", "FIM: nada")]))
    assert r.status == "definido" and r.preco_emb_med == 709.9 and "20/10" in r.motivo
    assert r.preco_data.day == 20 and r.imagem_url == "https://img/velha.jpg"


def test_nada_encontrado_explica_o_que_tentou(mundo):
    mundo({})
    r = rodar(MISTURADOR, cliente_llm=LLMFalso([("buscar", "deca link 1875"), ("fim", "FIM: nada")]))
    assert r.status == "nao_encontrado" and "deca link 1875" in r.motivo and r.preco_emb_med is None


def test_sem_agente_quando_desligado(mundo):
    mundo({}, padrao=[of("Magazine Luiza", 1878.78, "unidade")])
    llm = LLMFalso([])
    r = rodar(MISTURADOR, usar_agente=False, cliente_llm=llm)
    assert llm.chamadas == 0 and r.status == "definido" and r.iteracoes == 0


def test_erro_inesperado_vira_status_erro(mundo, monkeypatch):
    mundo({})
    async def quebra(*a, **k): raise RuntimeError("boom")
    monkeypatch.setattr(p, "buscar_e_extrair", quebra)
    r = rodar(TINTA, cliente_llm=LLMFalso([]))
    assert r.status == "erro" and "RuntimeError" in r.motivo


def test_varios_itens_avisam_cada_um_ao_terminar(mundo):
    mundo({}, padrao=[of("Telhanorte", 739.9), of("Magazine Luiza", 849.0)])
    prontos = []
    async def ao_terminar(r):
        prontos.append(r.item_id)
        if r.item_id == "b":
            raise RuntimeError("supabase fora")   # não pode derrubar os outros
    itens = [TINTA.model_copy(update={"id": x}) for x in "abc"]
    rs = asyncio.run(p.pesquisar_itens(itens, ao_terminar=ao_terminar, cliente_llm=LLMFalso([])))
    assert sorted(set(prontos)) == ["a", "b", "c"] and all(r.status == "definido" for r in rs)
    assert prontos.count("b") == 2   # a gravação falhou: tenta gravar "erro" para o item não ficar "buscando"


# ---------------------------------------------------------------- duas fases (achado da etapa 9)
CUBA = ItemEntrada(id="cuba", descricao="Cuba inox modelo raro", quantidade=1, unidade="un")


def _mundo_duas_fases(mundo):
    return mundo({"suvinil": [of("Telhanorte", 739.9), of("Magazine Luiza", 849.0), of("Sertão", 749.9)],
                  "deca link 1875": [of("Leroy Merlin", 1799.0, "unidade"), of("Loja Dexco", 1850.0, "unidade")],
                  "deca": [of("Magazine Luiza", 1878.78, "unidade")],
                  "cuba": []})


def test_fase1_avisa_todos_antes_do_agente_e_sem_preco_vai_primeiro(mundo, monkeypatch):
    """Itens rápidos aparecem antes de qualquer agente; com 1 loja aparece o provisório e depois o final;
    sem preço fica 'buscando' (não é avisado) até o agente terminar, e é o primeiro da fila do agente."""
    monkeypatch.setattr(p.get_settings(), "pesquisa_agentes_simultaneos", 1)
    _mundo_duas_fases(mundo)
    llm = LLMFalso([("buscar", "cuba inox outra loja"), ("fim", "FIM: nada"),           # cuba (sem preço) primeiro
                    ("buscar", "misturador Deca Link 1875 cozinha")])                    # depois o misturador
    eventos = []
    async def ao_terminar(r): eventos.append((r.item_id, r.status, r.iteracoes))
    rs = asyncio.run(p.pesquisar_itens([TINTA, MISTURADOR, CUBA], ao_terminar=ao_terminar, cliente_llm=llm))

    assert {e[0] for e in eventos[:2]} == {"1", "2"}, eventos               # fase 1: tinta + misturador provisório
    assert ("2", "definido", 0) in eventos[:2]
    assert eventos[2][0] == "cuba" and eventos[2][1] == "nao_encontrado"  # fase 2: sem preço primeiro
    assert eventos[3] == ("2", "definido", 1)                              # misturador refeito pelo agente
    assert [r.item_id for r in rs] == ["1", "2", "cuba"]                   # retorno na ordem de entrada
    assert rs[1].iteracoes == 1 and len(rs[1].fontes) == 3


def test_fase2_sem_prazo_fica_com_resultado_da_fase1(mundo, monkeypatch):
    monkeypatch.setattr(p.get_settings(), "pesquisa_prazo_agentes_s", 0)
    m = _mundo_duas_fases(mundo)
    llm = LLMFalso([])
    rs = asyncio.run(p.pesquisar_itens([MISTURADOR, CUBA], cliente_llm=llm))
    assert llm.chamadas == 0, "sem prazo o agente nem começa"
    assert rs[0].status == "definido" and rs[0].iteracoes == 0 and rs[0].confianca == "baixa"
    assert rs[1].status == "nao_encontrado"
    assert any(g[0] == MISTURADOR.descricao for g in m.gravados), "resultado final com preço vai para o cache"


def test_agente_usa_cota_propria_e_nao_a_das_extracoes(mundo, monkeypatch):
    """Com o porteiro das extrações todo ocupado, o agente ainda consegue chamar o LLM."""
    _mundo_duas_fases(mundo)
    from contextlib import AsyncExitStack

    from src import chaves_llm

    async def cenario():
        pool = chaves_llm.pool_extracao()
        async with AsyncExitStack() as ocupadas:
            for _ in range(len(pool.chaves) * pool.vagas):
                await ocupadas.enter_async_context(pool.vaga())   # extrações ocupando todas as vagas de todas as chaves
            llm = LLMFalso([("buscar", "misturador Deca Link 1875 cozinha")])
            return await asyncio.wait_for(p.pesquisar_item(MISTURADOR, cliente_llm=llm), timeout=5)

    r = asyncio.run(cenario())
    assert r.iteracoes == 1 and len(r.fontes) == 3


def test_cache_guarda_e_devolve_iteracoes_do_agente(mundo):
    entrada = EntradaCache(chave="x", descricao=MISTURADOR.descricao, imagem_url=None, provedor="tavily",
                           extracao=ResultadoExtracao(ofertas=[of("Magazine Luiza", 1878.78, "unidade"),
                                                               of("Leroy Merlin", 1799.0, "unidade")]),
                           atualizado_em=datetime.now(timezone.utc), vencido=False, iteracoes=2)
    mundo({}, cache_linha=entrada)
    assert rodar(MISTURADOR, cliente_llm=LLMFalso([])).iteracoes == 2   # a tela mostra "A IA refez a busca"

    m = _mundo_duas_fases(mundo)
    rodar(MISTURADOR, usar_cache=False, cliente_llm=LLMFalso([("buscar", "misturador Deca Link 1875 cozinha")]))
    assert m.iteracoes_gravadas == 1


@pytest.mark.parametrize("desc,trecho", [
    ("Tinta acrílica fosca vermelha", "acabamento"), ("Porcelanato 60x60 bege", "dimensão"),
    ("Torneira para cozinha", "código"), ("Cuba de apoio", "medidas"), ("Fechadura", "marca e modelo"),
])
def test_pergunta_certa_por_material(desc, trecho):
    assert trecho in p.pergunta_para(desc)


# ---------------------------------------------------------------- real (Tavily + Featherless + Supabase)
@pytest.mark.real
def test_etapa6_agente_real_refaz_quando_falta_loja():
    """Cenário controlado (a busca real varia: às vezes já vêm 3 lojas e o agente nem entra):
    a 1ª busca 'trouxe' só 1 loja, como na avaliação da etapa 4. O GLM-5.2 precisa reformular e achar mais."""
    consulta = "misturador cozinha deca preço"
    co = p.Coleta(consultas=[consulta])
    co.juntar([of("Magazine Luiza", 1878.78, "unidade", titulo="Misturador Monocomando Cozinha Link 2256 Deca"),
               of("Leroy Merlin", 990.5, "unidade", "parecido", "Misturador Deca Polo cozinha")])
    saida = asyncio.run(p.refazer_com_agente(MISTURADOR, co, p.resumo_para_agente(co.ofertas, co)))
    assert co.buscas_agente >= 1, f"o agente não refez a busca: {saida}"
    assert co.consultas[1].lower() != consulta and "deca" in co.consultas[1].lower(), co.consultas
    assert co.lojas_conferidas() >= 2, (saida, co.consultas, [(o.loja, o.preco, o.mesmo_produto) for o in co.ofertas])


@pytest.mark.real
def test_etapa6_item_completo_real():
    r = asyncio.run(p.pesquisar_item(MISTURADOR, usar_cache=False))
    assert r.status in ("definido", "pendente_especificacao"), r.motivo
    assert r.fontes and all(f.preco_embalagem > 0 for f in r.fontes) and r.iteracoes <= 2
