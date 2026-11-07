"""Gera mock.js com dados FICTÍCIOS no mesmo formato que a API vai devolver (usa as funções reais).
Rode da raiz do repo:  python -m front-resultado.gerar_mock   (ou: python front-resultado/gerar_mock.py)"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ganho import calcular_ganho  # noqa: E402
from src.logistica import Fornecedor, _haversine, calcular_logistica  # noqa: E402
from src.viabilidade import calcular_viabilidade  # noqa: E402

OBRA = {"nome": "Cozinha Planejada — Graças", "cep": "52011-050", "lat": -8.0453, "lon": -34.9029}
FORN = [
    Fornecedor(id="leroy", nome="Leroy Merlin Boa Viagem", dominio="leroymerlin.com.br", cep="51021-040",
               frete_base=29.9, rs_por_km=1.2, pedido_minimo=150, lat=-8.1226, lon=-34.8995),
    Fornecedor(id="cec", nome="C&C Boa Vista", dominio="cec.com.br", cep="50070-000",
               frete_base=24.0, rs_por_km=1.5, pedido_minimo=0, lat=-8.0616, lon=-34.8866),
    Fornecedor(id="telha", nome="Telhanorte Imbiribeira", dominio="telhanorte.com.br", cep="51150-000",
               frete_base=35.0, rs_por_km=1.0, pedido_minimo=200, lat=-8.1100, lon=-34.9100),
]
KM = {f.id: round(_haversine(OBRA["lat"], OBRA["lon"], f.lat, f.lon) * 1.3, 1) for f in FORN}
DOM = {"leroy": "leroymerlin.com.br", "cec": "cec.com.br", "telha": "telhanorte.com.br"}
NOME = {"leroy": "Leroy Merlin", "cec": "C&C", "telha": "Telhanorte"}


def item(desc, emb, qtd, precos, **x):
    fontes = [{"loja": NOME[k], "dominio": DOM[k], "url": f"https://www.{DOM[k]}/produto/exemplo",
               "preco_embalagem": p} for k, p in precos.items()]
    v = list(precos.values())
    return {"descricao": desc, "categoria": x.pop("categoria", "Materiais"), "embalagem": emb, "qtd_embalagens": qtd,
            "status": "definido", "confianca": x.pop("confianca", "alta"), "estimativa": False,
            "preco_emb_min": min(v), "preco_emb_med": round(statistics.median(v), 2), "preco_emb_max": max(v),
            "fontes": fontes, **x}


BASE = [
    item("Tinta acrílica Coral Decora Cinza Urbano", "lata 18 L", 2, {"leroy": 489.9, "cec": 512.0, "telha": 499.0}),
    item("Porcelanato Portobello Cimento 90x90", "caixa 1,62 m²", 33, {"leroy": 118.9, "cec": 112.5, "telha": 121.0}),
    item("Argamassa colante AC-III Quartzolit", "saco 20 kg", 15, {"leroy": 36.9, "cec": 38.5, "telha": 34.9}, confianca="média"),
    item("Rejunte Quartzolit cinza platina", "saco 5 kg", 5, {"leroy": 49.9, "cec": 47.0}),
    item("Cuba de cozinha inox 56x34", "unidade", 1, {"leroy": 389.0, "telha": 365.0}, confianca="baixa"),
    item("Monocomando Deca para cozinha", "unidade", 1, {"cec": 459.0}, confianca="baixa"),
    {"descricao": "Tinta vermelha para parede da copa", "categoria": "Pintura", "status": "pendente_especificacao",
     "estimativa": True, "embalagem": "lata 18 L", "qtd_embalagens": 1, "preco_emb_min": 380, "preco_emb_med": 460,
     "preco_emb_max": 560, "confianca": "baixa", "fontes": [],
     "pergunta": "Qual acabamento e litragem da tinta vermelha?"},
]
SEM_PRECO = [{"descricao": "Painel ripado freijó sob medida", "categoria": "Marcenaria", "status": "nao_encontrado",
              "fontes": []},
             {"descricao": "Bancada de granito Branco Itaúnas", "categoria": "Marcenaria", "status": "buscando",
              "fontes": []}]


def cenario(nome, itens, orcamento, segundos, custo_usd):
    lg = calcular_logistica(itens, FORN, KM)
    vi = calcular_viabilidade(itens, orcamento, lg.frete_total if lg else 0)
    return {"id": nome, "nome": OBRA["nome"], "cep": OBRA["cep"], "orcamento_cliente": orcamento, "itens": itens,
            "logistica": lg.model_dump() if lg else None, "viabilidade": vi.model_dump(),
            "ganho": calcular_ganho(len(itens), segundos, custo_usd).model_dump()}


MOCKS = {
    "cabe": cenario("cabe", BASE, 9000, 28, 0.054),
    "nao-cabe": cenario("nao-cabe", BASE, 5500, 31, 0.061),
    "parcial": cenario("parcial", BASE + SEM_PRECO, 9000, 19, 0.047),
}
saida = Path(__file__).with_name("mock.js")
saida.write_text("// GERADO por gerar_mock.py: dados fictícios no formato da API\nwindow.MOCKS = "
                 + json.dumps(MOCKS, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
for k, m in MOCKS.items():
    v, lg = m["viabilidade"], m["logistica"]
    print(k, "|", lg["estrategia"], f'frete {lg["frete_total"]} econ {lg["economia_estimada"]}', "|", v["resumo"][:90])
