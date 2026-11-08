"""Etapa 8 — componentes do item (ItemRow + cota de preço): coerência com o contrato do backend,
regras da skill de design e checagem de tipos do TypeScript."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from src.modelos import Fonte, ResultadoItem

RAIZ = Path(__file__).resolve().parents[2]
UI = RAIZ / "ui-fatia-b"
COMP = UI / "src" / "components" / "orcamento"
SITE = RAIZ / "frontend"                                   # site Next.js do time (fatia A)
COMP_SITE = SITE / "src" / "components" / "orcamento"      # cópia oficial dos componentes da B no site
COMPARTILHADOS = ["tipos.ts", "formato.ts", "StatusBadge.tsx", "PriceDimension.tsx", "ItemRow.tsx", "orcamento.css"]
COMPARTILHADOS += ["../imagens/ImagemProduto.tsx", "../imagens/imagem.ts", "../imagens/imagem.module.css"]


def test_site_e_previa_usam_os_mesmos_componentes():
    """A prévia (ui-fatia-b) e o site (frontend) não podem divergir: mude no site e copie para a prévia."""
    diferentes = [f for f in COMPARTILHADOS
                  if (COMP / f).read_text(encoding="utf-8") != (COMP_SITE / f).read_text(encoding="utf-8")]
    assert not diferentes, f"copie de frontend/src/components/orcamento para ui-fatia-b: {diferentes}"


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
    arquivos = [a for pasta in (COMP, COMP_SITE) for a in list(pasta.glob("*.tsx")) + list(pasta.glob("*.css"))]
    for arquivo in arquivos:
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
    r = subprocess.run("npx tsc --noEmit", cwd=UI, shell=True, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_papeis_de_cor_do_site_cobrem_todos_os_papeis():
    """Os componentes só funcionam no site se todos os papéis tiverem valor (src/styles/papeis-de-cor.css)."""
    css = (SITE / "src" / "styles" / "papeis-de-cor.css").read_text(encoding="utf-8")
    definidos = set(re.findall(r"--(cor-[a-z0-9-]+)\s*:", css))
    usados = {v for a in COMP_SITE.glob("*.css") for v in re.findall(r"var\(--(cor-[a-z0-9-]+)", a.read_text(encoding="utf-8"))}
    assert usados <= definidos, f"papel sem valor no site: {usados - definidos}"


@pytest.mark.skipif(not (SITE / "node_modules").exists() or not shutil.which("npx"),
                    reason="rode `npm install` em frontend para checar tipos e testes do site")
def test_site_compila_e_passa_nos_testes():
    for comando in ("npx tsc --noEmit", "npx vitest run"):
        r = subprocess.run(comando, cwd=SITE, shell=True, capture_output=True,
                           encoding="utf-8", errors="replace", timeout=180)
        assert r.returncode == 0, f"{comando}\n{r.stdout[-2000:]}{r.stderr[-2000:]}"
