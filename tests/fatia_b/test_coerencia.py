"""Coerência da Fatia B com o resto do programa (roda em toda revisão, offline).

Confere o código contra os documentos combinados com o time, para nenhuma fatia
"falar outra língua" sem ninguém perceber.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest

from src.modelos import Fonte, ResultadoItem, Status
from src.tools import ToolArgs, registry

RAIZ = Path(__file__).resolve().parents[2]
PADRAO_CHAVE = re.compile(r"tvly-[A-Za-z0-9_-]{20,}|sk-lf-[0-9a-f-]{20,}|pk-lf-[0-9a-f-]{20,}"
                          r"|rc_[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9_-]{10,}|eyJhbGciOi[A-Za-z0-9_-]{20,}")
FATIAS = (RAIZ / "docs" / "FATIAS-DO-TIME.md").read_text(encoding="utf-8")


def _linha_contrato(rotulo: str) -> str:
    for linha in FATIAS.splitlines():
        if linha.startswith(f"| {rotulo} |"):
            return linha
    pytest.fail(f"linha '{rotulo}' não encontrada na tabela de contratos de docs/FATIAS-DO-TIME.md")


def _campos_documentados(linha: str) -> set[str]:
    nomes: set[str] = set()
    for trecho in re.findall(r"`([^`]+)`", linha):
        for nome in re.findall(r"[a-z_]+(?:/[a-z]+)*", trecho):
            if "/" in nome:  # preco_emb_min/med/max -> 3 campos
                base, *sufixos = nome.split("/")
                prefixo = base.rsplit("_", 1)[0]
                nomes |= {base} | {f"{prefixo}_{s}" for s in sufixos}
            else:
                nomes.add(nome)
    return nomes


def test_campos_b_para_c_existem_no_modelo():
    documentados = _campos_documentados(_linha_contrato("B → C"))
    no_codigo = set(ResultadoItem.model_fields) | set(Fonte.model_fields)
    faltando = documentados - no_codigo
    assert not faltando, f"o contrato B → C cita campos que o modelo não tem: {sorted(faltando)}"


def test_status_iguais_ao_documento():
    documentados = set(re.findall(r"`([a-z_]+)`", _linha_contrato("Todos")))
    no_codigo = set(typing.get_args(Status))
    assert documentados == no_codigo, f"documento={sorted(documentados)} código={sorted(no_codigo)}"


def test_regra_nunca_preco_sem_fonte():
    with pytest.raises(ValueError, match="preço sem fonte"):
        ResultadoItem(item_id="1", status="definido", preco_emb_min=10, preco_emb_med=12, preco_emb_max=15)


def test_pendente_exige_pergunta_e_falha_exige_motivo():
    with pytest.raises(ValueError, match="pergunta"):
        ResultadoItem(item_id="1", status="pendente_especificacao")
    with pytest.raises(ValueError, match="motivo"):
        ResultadoItem(item_id="1", status="nao_encontrado")


def test_resultado_valido_passa():
    fonte = Fonte(loja="Leroy Merlin", dominio="leroymerlin.com.br", url="https://www.leroymerlin.com.br/x", preco_embalagem=189.9)
    r = ResultadoItem(item_id="1", status="definido", preco_emb_min=180, preco_emb_med=189.9, preco_emb_max=210,
                      fontes=[fonte], confianca="alta", embalagem="caixa 1,62 m²", qtd_embalagens=33)
    assert r.status == "definido"


def test_ferramentas_seguem_a_skill_react():
    """skills/01: toda tool recebe argumentos que herdam ToolArgs (rejeita campo inventado pelo LLM)."""
    for nome in registry.names():
        tool = registry._tools[nome]
        assert issubclass(tool.args_model, ToolArgs), f"tool '{nome}' não usa ToolArgs"
        assert len(tool.description) >= 20, f"tool '{nome}' precisa de descrição dizendo quando usar"


def test_sem_chaves_no_codigo():
    # Chaves reais do Tavily têm hífens (tvly-dev-…, ~58 caracteres); fakes de teste são curtas.
    padrao = PADRAO_CHAVE
    vazou = [str(p.relative_to(RAIZ)) for pasta in ("src", "scripts", "prompts", "tests")
             for p in (RAIZ / pasta).rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".mjs")
             and padrao.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert not vazou, f"chave de API escrita no código: {vazou}"
