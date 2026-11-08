"""Auditoria de TODOS os botões do resultado (fatia B), com pesquisa REAL e banco em memória (não grava no Supabase).

Para cada item da demo (docs/arquivos-teste/demo-jurados.json) aperta: pesquisa inicial, Pesquisar de novo, as 3
alternativas, Voltar para o anterior (quando trocou), Responder e Usar a média (quando pendente), e confere o resultado:
status válido, faixa de preço, pelo menos uma loja confirmada (ou o aviso), pergunta/motivo e o título.

Uso (gasta crédito do Serper/Tavily/Featherless; ~20 min para a demo):
    python -m scripts.auditar_botoes            # itens da demo
    python -m scripts.auditar_botoes --qualquer # entradas estranhas (texto sem sentido, números, emoji...)
"""
import asyncio
import json
import sys
import time
import logging

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.ERROR)
import src  # noqa: E402,F401
from src.alternativas import AlternativaIndisponivel  # noqa: E402
from src.modelos import ItemEntrada, ResultadoItem  # noqa: E402
from src.orcamento import CLASSIFICACAO_DA_A, repesquisar_item  # noqa: E402
from src.pesquisa import pesquisar_item  # noqa: E402
from src.revisao import classificar_item  # noqa: E402

RESPOSTAS = {   # o que um arquiteto escreveria em "Responder"
    "porcelanato": "Porcelanato Portobello 60x60 polido", "tinta": "Tinta Suvinil Fosco Completo branco 18L",
    "tomada": "Tomada Tramontina Liz 20A branca", "joelho": "Joelho Tigre soldável 25mm 90 graus",
    "spot": "Spot LED Stella 7W 3000K", "azulejo": "Azulejo Eliane Paris azul 20x20",
}


class Banco:
    def __init__(self, item: ItemEntrada, atual: ResultadoItem | None):
        self.it, self.atual, self.marcados = item, atual, []

    async def item(self, item_id): return self.it
    async def orcamento_do_item(self, item_id): return None
    async def resultado_atual(self, item_id): return self.atual
    async def somar_custo(self, *a): pass

    async def marcar_item(self, item_id, campos):
        self.marcados.append(campos)
        upd = {}
        if "descricao" in campos:
            upd["descricao"] = campos["descricao"]
        if "classificacao" in campos:
            upd["classificacao"] = CLASSIFICACAO_DA_A.get(campos["classificacao"], "definido")
        if upd:
            self.it = self.it.model_copy(update=upd)

    async def gravar_item(self, r): self.atual = r


def problemas(r: ResultadoItem | None) -> list[str]:
    if r is None:
        return ["sem resultado"]
    p = []
    if r.status == "erro":
        p.append(f"status erro: {r.motivo}")
    if r.status == "buscando":
        p.append("ficou buscando")
    if r.preco_emb_med is not None:
        if not (r.preco_emb_min <= r.preco_emb_med <= r.preco_emb_max) or r.preco_emb_med <= 0:
            p.append("faixa de preço inválida")
        if not r.fontes:
            p.append("preço sem fonte")
        elif not any(f.link_verificado for f in r.fontes) and not (
                r.estimativa and "não confirmado" in (r.motivo or "").lower()):
            p.append("preço sem nenhum link confirmado (e sem aviso)")
    if r.status == "definido" and r.preco_emb_med is None:
        p.append("definido sem preço")
    if r.status == "pendente_especificacao" and not r.pergunta:
        p.append("pendente sem pergunta")
    if r.status == "nao_encontrado" and not r.motivo:
        p.append("não encontrado sem motivo")
    return p


def resumo(r):
    if r is None:
        return "-"
    lojas = f"{sum(f.link_verificado for f in r.fontes)}/{len(r.fontes)} conf."
    if r.preco_emb_med is not None and not any(f.link_verificado for f in r.fontes):
        lojas += " AVISO:sem-confirmacao"
    return f"{r.status} R$ {r.preco_emb_med} {lojas} | {r.produto_normalizado or ''}"[:120]


async def botao(nome, item, inicial, **kw):
    banco = Banco(item, inicial)
    t = time.perf_counter()
    troca = {} if kw.get("objetivo") else None
    try:
        r = await repesquisar_item(item.id, banco=banco, troca=troca, **kw) if troca is not None \
            else await repesquisar_item(item.id, banco=banco, **kw)
    except AlternativaIndisponivel as e:
        return {"botao": nome, "ok": True, "obs": f"IA sem sugestão (tela mostra a mensagem): {e}", "s": time.perf_counter() - t}
    except Exception as e:  # noqa: BLE001
        return {"botao": nome, "ok": False, "obs": f"EXCEÇÃO {type(e).__name__}: {e}", "s": time.perf_counter() - t}
    p = problemas(r)
    obs = resumo(r)
    extra = None
    if troca:
        obs += f" | trocou={troca.get('trocou')} -> {troca.get('agora')}"
        if troca.get("trocou"):
            if banco.it.descricao != troca["agora"]:
                p.append("título não mudou para o sugerido")
            extra = (troca["antes"]["descricao"], banco.it, r)
        elif r.motivo is None:
            p.append("não trocou e não explicou")
    if kw.get("voltar_para") and banco.it.descricao != kw["voltar_para"]:
        p.append("voltar não restaurou o título")
    return {"botao": nome, "ok": not p, "obs": obs + ("" if not p else " || " + "; ".join(p)), "s": time.perf_counter() - t,
            "extra": extra}


async def auditar(desc, q, u, cat, completo=True):
    cls = CLASSIFICACAO_DA_A.get(classificar_item(desc), "definido")
    item = ItemEntrada(id="1", descricao=desc, quantidade=q, unidade=u, categoria=cat, classificacao=cls)
    try:
        inicial = await pesquisar_item(item, usar_cache=True)
    except Exception as e:  # noqa: BLE001
        return desc, [{"botao": "pesquisa inicial", "ok": False, "obs": f"EXCEÇÃO {type(e).__name__}: {e}"}]
    linhas = [{"botao": "pesquisa inicial", "ok": not problemas(inicial),
               "obs": resumo(inicial) + ("" if not problemas(inicial) else " || " + "; ".join(problemas(inicial)))}]
    tarefas = [botao("pesquisar de novo", item, inicial)]
    objetivos = ("qualidade", "preco", "semelhante") if completo else ("preco",)
    tarefas += [botao(f"alternativa {o}", item, inicial, objetivo=o) for o in objetivos]
    if inicial.status == "pendente_especificacao":
        resp = next((v for k, v in RESPOSTAS.items() if k in desc.lower()), f"{desc} marca Tramontina")
        tarefas.append(botao("responder", item, inicial, nova_descricao=resp))
        if inicial.preco_emb_med is not None:
            tarefas.append(botao("usar a média", item, inicial, aceitar_media=True))
    feitos = await asyncio.gather(*tarefas)
    voltas = []
    for f in feitos:
        if f.get("extra"):
            antes, it_novo, r_novo = f["extra"]
            voltas.append(botao(f"voltar ({f['botao']})", it_novo, r_novo, voltar_para=antes))
    feitos += await asyncio.gather(*voltas)
    for f in feitos:
        f.pop("extra", None)
    return desc, linhas + feitos


async def main():
    demo = json.load(open("docs/arquivos-teste/demo-jurados.json", encoding="utf-8"))
    vistos, itens = set(), []
    for linhas in demo.values():
        for a, q, u, c in linhas:
            if (a, u) not in vistos:
                vistos.add((a, u))
                itens.append((a, q, u, c, True))
    if "--qualquer" in sys.argv:
        itens = [("xyzabc qwerty", 3, "un", None, False), ("12345", 1, "un", None, False),
                 ("Cimento", 10, "un", "Alvenaria", False), ("Tinta 😀 azul céu", 20, "m2", "Pintura", False),
                 ("Bacia sanitária Deca Vogue Plus com caixa acoplada", 2, "un", "Louças", False),
                 ("Fio 2,5mm", 100, "m", "Elétrica", False),
                 ("Piso vinílico " + "muito resistente " * 12, 30, "m2", None, False),
                 ("Telha", 0.5, "m3", None, False)]
    porteiro = asyncio.Semaphore(4)

    async def um(x):
        async with porteiro:
            return await auditar(*x[:4], completo=x[4])

    total = falhas = 0
    for desc, linhas in await asyncio.gather(*(um(x) for x in itens)):
        print(f"\n== {desc[:60]}")
        for l in linhas:
            total += 1
            falhas += not l["ok"]
            print(f"  {'OK ' if l['ok'] else 'FALHA'} {l['botao']:28} {l['obs']}")
    print(f"\nTOTAL: {total - falhas}/{total} ok, {falhas} falhas")


asyncio.run(main())
