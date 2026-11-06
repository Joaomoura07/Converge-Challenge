"""Confere o ambiente ANTES do evento: Featherless (chat + tool calling), Langfuse e Supabase.

    python -m scripts.check_setup                     # testa FEATHERLESS_MODEL
    python -m scripts.check_setup --model Qwen/Qwen3-32B

Gasta poucos centavos de crédito (2 chamadas curtas).
"""

from __future__ import annotations

import argparse
import json
import sys

from src.agent import build_llm_client
from src.config import get_settings

OK, FAIL, WARN = "[OK]  ", "[FAIL]", "[WARN]"


def check_featherless(model: str) -> bool:
    client = build_llm_client()
    try:
        # GLM e outros modelos de raciocínio gastam tokens "pensando" antes de responder
        r = client.chat.completions.create(model=model, max_tokens=300,
                                           messages=[{"role": "user", "content": "Responda só: pong"}])
        u = r.usage
        print(f"{OK} chat {model}: {r.choices[0].message.content!r} | tokens {u.prompt_tokens}+"
              f"{u.completion_tokens} | custo US$ {getattr(u, 'cost', 'n/d')}")
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL} chat {model}: {exc}  (401=chave, 403=desbloquear modelo, 400=modelo frio)")
        return False

    tool = {"type": "function", "function": {
        "name": "get_weather", "description": "Clima de uma cidade",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}
    try:
        r = client.chat.completions.create(model=model, tools=[tool], max_tokens=200,
                                           messages=[{"role": "user", "content": "Como está o clima em Recife?"}])
        calls = r.choices[0].message.tool_calls
        if calls:
            print(f"{OK} tool calling nativo: {calls[0].function.name}({calls[0].function.arguments})")
        else:
            print(f"{WARN} {model} respondeu sem tool_calls -> use FEATHERLESS_MODEL_FALLBACK ou o modo JSON "
                  f"(skills/01-react-agent-pattern.md)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL} tool calling {model}: {exc}")
        return False


def check_langfuse() -> bool:
    s = get_settings()
    if not s.langfuse_enabled:
        print(f"{WARN} Langfuse: desligado por LANGFUSE_ENABLED=false")
        return True
    if not s.langfuse_configured:
        print(f"{WARN} Langfuse: chaves ausentes ou placeholder (tracing desativado). "
              f"Pegue as reais em Settings -> API Keys do projeto no Langfuse")
        return False
    from langfuse import get_client
    try:
        ok = get_client().auth_check()
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL} Langfuse: {type(exc).__name__}. Chave errada ou região errada "
              f"(LANGFUSE_HOST EU=cloud.langfuse.com / US=us.cloud.langfuse.com)")
        return False
    print(f"{OK if ok else FAIL} Langfuse auth ({get_settings().langfuse_host})")
    return ok


def check_supabase() -> bool:
    if not get_settings().supabase_configured:
        print(f"{WARN} Supabase: URL/KEY ausentes")
        return False
    from src.database import get_supabase
    try:
        get_supabase().table("agent_runs").select("id").limit(1).execute()
        print(f"{OK} Supabase: tabela agent_runs acessível")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL} Supabase: {exc}  (rodou sql/001_agent_runs.sql?)")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=get_settings().featherless_model)
    args = parser.parse_args()
    if not get_settings().llm_configured:
        print(f"{FAIL} FEATHERLESS_API_KEY ausente no .env")
        return 1
    results = [check_featherless(args.model), check_langfuse(), check_supabase()]
    print(json.dumps({"featherless": results[0], "langfuse": results[1], "supabase": results[2]}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
