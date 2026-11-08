"""Bytes reais -> JSON do frontend -> A/B/C -> Excel/PDF, no máximo 10 itens.

Execute fluxo-curto.test.ts antes para verificar os JSONs de contrato. Banco e preços
são simulados; rotas, persistência via adaptador, revisão, cálculo e exportação são reais.
"""
import json
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

import test_fluxo_a_b_c as fluxo
from test_fluxo_a_b_c import mundo  # fixture do banco em memória compartilhado por A, B e C

DIR = Path(__file__).parent / 'importacao/fixtures/fluxo-curto'


@pytest.mark.parametrize('formato', ['pdf', 'dxf', 'ifc', 'skp'])
def test_arquivo_revisado_ate_exportacao(mundo, monkeypatch, formato):
    pedido = json.loads((DIR / f'{formato}-envio.json').read_text(encoding='utf-8'))
    assert 1 <= len(pedido['itens']) <= 10
    monkeypatch.setattr(fluxo, 'preco_sintetico', lambda item: fluxo._definido(
        item.id, item.descricao, 'embalagem de teste', 8, 10.0, 12.0, 14.0, fluxo.LEROY))
    r = mundo.api.post('/orcamentos', json=pedido)
    assert r.status_code == 200, r.text
    orc = mundo.bd.tabelas['orcamentos'][0]
    gravados = mundo.bd.tabelas['orcamento_itens']
    assert orc['status_pesquisa'] == 'concluida'
    assert orc['viabilidade']['total_med'] == pytest.approx(len(pedido['itens']) * 8 * 12)
    assert orc['viabilidade']['completo'] is True
    for enviado, gravado in zip(pedido['itens'], gravados):
        for chave in ['quantidade', 'unidade', 'descricao_original', 'nivel', 'extras']:
            assert gravado[chave] == enviado[chave]
        assert gravado['status'] == 'definido' and gravado['fontes']
    # Idempotência: o mesmo pedido não cria mais linhas; alteração exige outro ID.
    assert mundo.api.post('/orcamentos', json=pedido).status_code == 200
    assert len(gravados) == len(pedido['itens'])
    pedido['itens'][0]['quantidade'] = 9.0
    assert mundo.api.post('/orcamentos', json=pedido).status_code == 409
    for extensao in ['xlsx', 'pdf']:
        arquivo = mundo.api.get(f'/orcamentos/{pedido["orcamento_id"]}/exportar.{extensao}')
        assert arquivo.status_code == 200, arquivo.text
        if extensao == 'pdf':
            assert arquivo.content.startswith(b'%PDF-') and len(arquivo.content) > 1000
        else:
            wb = load_workbook(BytesIO(arquivo.content))
            texto = ' '.join(str(c.value) for ws in wb for linha in ws for c in linha if c.value is not None)
            assert 'Teste sintético' in texto and 'leroymerlin.com.br' in texto


@pytest.mark.parametrize('formato', ['pdf', 'dxf', 'ifc', 'skp'])
def test_quantidade_pendente_nao_chega_a_pesquisa(mundo, formato):
    pedido = json.loads((DIR / f'{formato}-envio.json').read_text(encoding='utf-8'))
    pedido['itens'][0]['quantidade'] = None
    assert mundo.api.post('/orcamentos', json=pedido).status_code == 422
    assert mundo.bd.tabelas['orcamentos'] == []
