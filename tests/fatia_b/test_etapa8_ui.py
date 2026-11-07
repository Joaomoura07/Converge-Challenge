"""Etapa 8 — componentes do item (ItemRow + cota de preço): coerência com o contrato do backend,
regras da skill de design e checagem de tipos do TypeScript."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from src.modelos import Fonte, ResultadoItem

UI = Path(__file__).resolve().parents[2] / "ui-fatia-b"
COMP = UI / "src" / "components" / "orcamento"


def _campos_ts(interface: str) -> set[str]:
    texto = (COMP / "tipos.ts").read_text(encoding="utf-8")
    corpo = re.search(rf"interface {interface} \{{(.*?)\n\}}", texto, re.S).group(1)
    return set(re.findall(r"^\s+(\w+)\??:", corpo, re.M))


def test_tipos_do_site_batem_com_o_contrato_do_backend():
    """Se o backend ganhar ou perder um campo, o tipo do site precisa acompanhar (e vice-versa)."""
    backend = set(ResultadoItem.model_fields) - {"item_id"}
    site = _campos_ts("ItemOrcamento") - {"id", "descricao", "quantidade", "unidade"}   # colunas da fatia A
    assert site == backend, f"só no site: {site - backend} · só no backend: {backend - site}"
    assert _campos_ts("Fonte") == set(Fonte.model_fields)


def test_status_do_site_iguais_aos_do_backend():
    texto = (COMP / "tipos.ts").read_text(encoding="utf-8")
    site = set(re.findall(r'"(\w+)"', re.search(r"type StatusItem = (.*?);", texto).group(1)))
    assert site == set(ResultadoItem.model_fields["status"].annotation.__args__)


def test_componentes_usam_so_papeis_de_cor():
    """Skill de design, seção 2 e 7: nada de hex direto no componente; as cores vêm de var(--cor-...)."""
    for arquivo in list(COMP.glob("*.tsx")) + list(COMP.glob("*.css")):
        texto = arquivo.read_text(encoding="utf-8")
        hexes = [h for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", texto) if h.lower() != "#fff"]
        assert not hexes, f"{arquivo.name} tem cor fixa: {hexes}"
        variaveis = set(re.findall(r"var\(--(cor-[a-z0-9-]+)", texto))
        assert variaveis <= {"cor-fundo", "cor-superficie", "cor-texto", "cor-texto-2", "cor-linha", "cor-acao",
                             "cor-definido", "cor-pendente", "cor-erro"}, variaveis


def test_respeita_movimento_reduzido_e_tem_modo_demo():
    css = (COMP / "orcamento.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in css and ".orc-demo" in css


@pytest.mark.skipif(not (UI / "node_modules").exists() or not shutil.which("npx"),
                    reason="rode `npm install` em ui-fatia-b para checar os tipos")
def test_typescript_compila():
    r = subprocess.run("npx tsc --noEmit", cwd=UI, shell=True, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
