"""Revisão de etapa da Fatia B: executa, testa e confere coerência. Registra em docs/revisao/fatia-b.md.

    python -m scripts.revisar --etapa 1 --nota "configuração"          # só checagens offline
    python -m scripts.revisar --etapa 1 --real --nota "configuração"   # + chamadas reais (gasta créditos)

Checagens:
  1. sintaxe     — todo .py de src/ e scripts/ compila
  2. testes      — pytest offline inteiro (Fatia B + 100 casos de importação): nada antigo quebrou
  3. coerência   — tests/fatia_b/test_coerencia.py (contrato do FATIAS-DO-TIME.md, regras das skills, sem chaves)
  4. api         — a API sobe e GET /health responde 200
  5. real        — (com --real) testes marcados `real` da etapa: chamadas de verdade
"""

from __future__ import annotations

import argparse
import os
import py_compile
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "docs" / "revisao" / "fatia-b.md"


def _pytest(*args: str) -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *args],
                       cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    saida = (r.stdout + r.stderr).strip().splitlines()
    resumo = next((l for l in reversed(saida) if " passed" in l or " failed" in l or " error" in l
                   or "no tests ran" in l), saida[-1] if saida else "")
    falhas = [l for l in saida if l.startswith(("FAILED", "ERROR", "SKIPPED"))]
    return r.returncode in (0, 5), resumo.strip("= ") + ("\n" + "\n".join(falhas[:8]) if falhas else "")


def checar_sintaxe() -> tuple[bool, str]:
    erros = []
    for pasta in ("src", "scripts"):
        for f in (RAIZ / pasta).rglob("*.py"):
            try:
                py_compile.compile(str(f), doraise=True)
            except py_compile.PyCompileError as e:
                erros.append(f"{f.relative_to(RAIZ)}: {e.msg.splitlines()[-1]}")
    return not erros, "todos os arquivos compilam" if not erros else "\n".join(erros)


def checar_api() -> tuple[bool, str]:
    sys.path.insert(0, str(RAIZ))
    try:
        from fastapi.testclient import TestClient
        from src.main import app
        r = TestClient(app).get("/health")
        j = r.json()
        ok = r.status_code == 200
        return ok, f"HTTP {r.status_code} · llm={j.get('llm')} supabase={j.get('supabase')} langfuse={j.get('langfuse')}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", required=True)
    ap.add_argument("--nota", default="")
    ap.add_argument("--real", action="store_true", help="roda também os testes que chamam serviços de verdade")
    a = ap.parse_args()
    # Terminal do Windows usa cp1252 e não imprime ✅/❌; força UTF-8 na saída.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    inicio = time.perf_counter()
    resultados: list[tuple[str, bool, str]] = []
    resultados.append(("sintaxe", *checar_sintaxe()))
    resultados.append(("testes (offline, tudo)", *_pytest()))
    resultados.append(("coerência com o programa", *_pytest("tests/fatia_b/test_coerencia.py")))
    resultados.append(("api /health", *checar_api()))
    if a.real:
        ok, det = _pytest("tests/fatia_b", "-m", "real", "-k", f"etapa{a.etapa}", "-rs")
        if ok and " passed" not in det.splitlines()[0]:
            ok = None   # só pulou (ex.: tabela ainda não criada): não executou de verdade, então não aprova
        resultados.append((f"execução real (etapa {a.etapa})", ok, det))
    dur = time.perf_counter() - inicio

    reprovado = any(ok is False for _, ok, _ in resultados)
    pendente = not reprovado and any(ok is None for _, ok, _ in resultados)
    aprovado = not reprovado and not pendente
    veredito = "APROVADA" if aprovado else "PENDENTE (algo não rodou de verdade)" if pendente else "REPROVADA"
    icone = {True: "✅", False: "❌", None: "⏸️"}
    print(f"\nREVISÃO — etapa {a.etapa} {('— ' + a.nota) if a.nota else ''}")
    for nome, ok, det in resultados:
        print(f"  {icone[ok]} {nome}: {det.splitlines()[0] if det else ''}")
        for extra in det.splitlines()[1:]:
            print(f"       {extra}")
    print(f"  {veredito} em {dur:.1f} s")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text("# Revisões da Fatia B (pesquisa de preço)\n\nCada etapa só avança com revisão aprovada. "
                       "Gerado por `python -m scripts.revisar`.\n", encoding="utf-8")
    linhas = [f"\n## Etapa {a.etapa}{(' — ' + a.nota) if a.nota else ''} · {datetime.now():%d/%m %H:%M} · "
              f"{icone[True if aprovado else None if pendente else False]} {veredito.lower()}", "", "| Checagem | Resultado | Detalhe |", "|---|---|---|"]
    for nome, ok, det in resultados:
        linhas.append(f"| {nome} | {icone[ok]} | {det.replace(chr(10), '<br>').replace('|', '/')} |")
    with LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    return 0 if aprovado else 2 if pendente else 1


if __name__ == "__main__":
    sys.exit(main())
