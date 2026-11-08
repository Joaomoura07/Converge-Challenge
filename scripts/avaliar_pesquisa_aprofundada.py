"""Amostra pequena: --live chama serviços reais; não grava orçamento nem cache remoto."""
import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.config import get_settings
from src.custo import acumular
from src.modelos import ItemEntrada
from src.pesquisa import pesquisar_item


async def avaliar():
    s = get_settings()
    s.pesquisa_max_refazer = 1
    s.pesquisa_max_chamadas_item = 3
    s.pesquisa_max_chamadas_execucao = 6
    s.pesquisa_max_tokens_execucao = 30000
    s.pesquisa_limite_usd_execucao = 0.02
    s.pesquisa_hedge_ativo = False
    resultados = []
    with acumular() as total, patch("src.pesquisa.cache.gravar", new=AsyncMock(return_value=False)):
        for i, descricao in enumerate(["Tomada Tramontina Liz branca 20A", "Tinta Suvinil Toque de Seda Branco Neve 18 L"]):
            r = await pesquisar_item(ItemEntrada(id=f"avaliacao-sintetica-{i}", descricao=descricao,
                                                quantidade=1, unidade="un", classificacao="definido"), usar_cache=False)
            registro = {"produto": descricao, "status": r.status, "motivo": r.motivo,
                        "fontes": [f.model_dump() for f in r.fontes], "consumo": r.pesquisa_detalhes}
            resultados.append(registro)
            print(json.dumps(registro, ensure_ascii=False), flush=True)
    relatorio = {"data": "2026-11-08", "consumo_total": total.resumo(), "resultados": resultados}
    Path("reports/avaliacao-pesquisa-aprofundada.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"consumo_total": total.resumo()}, ensure_ascii=False), flush=True)
    from langfuse import get_client
    get_client().flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="autoriza a amostra real limitada")
    if not parser.parse_args().live:
        parser.error("use --live para fazer a amostra real")
    asyncio.run(avaliar())
