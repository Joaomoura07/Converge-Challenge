"""Registro de ferramentas do agente.

Cada ferramenta é uma função que recebe UM modelo Pydantic com os argumentos.
O schema JSON (function calling) é gerado automaticamente a partir desse modelo.

    class MinhaArgs(BaseModel):
        campo: str = Field(description="...")

    @registry.tool(description="O que a ferramenta faz e quando usar.")
    def minha_ferramenta(args: MinhaArgs) -> dict:
        ...
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, get_type_hints
from zoneinfo import ZoneInfo

from langfuse import observe
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

ESCALATE_TOOL = "escalate_to_human"


class ToolArgs(BaseModel):
    """Base para argumentos de ferramentas: rejeita campos inventados pelo LLM."""

    model_config = ConfigDict(extra="forbid")


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[BaseModel], Any]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def tool(self, description: str, name: str | None = None):
        def decorator(fn: Callable):
            params = list(inspect.signature(fn).parameters)
            hints = get_type_hints(fn)
            args_model = hints.get(params[0]) if params else None
            if not (isinstance(args_model, type) and issubclass(args_model, BaseModel)):
                raise TypeError(f"{fn.__name__}: o 1º parâmetro deve ser um BaseModel")
            tool_name = name or fn.__name__
            self._tools[tool_name] = Tool(tool_name, description, args_model, fn)
            return fn

        return decorator

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    @observe(as_type="tool", name="tool.execute")
    def execute(self, name: str, raw_args: str | dict) -> dict:
        """Executa a ferramenta. Nunca levanta exceção: erros voltam ao LLM como dados,
        para que o agente possa se corrigir ou escalar."""
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Ferramenta desconhecida: {name}"}
        try:
            data = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            args = tool.args_model.model_validate(data or {})
        except (json.JSONDecodeError, ValidationError) as exc:
            return {"ok": False, "error": f"Argumentos inválidos: {exc}"}
        try:
            return {"ok": True, "result": tool.fn(args)}
        except Exception as exc:  # noqa: BLE001 — a falha vira observação p/ o agente
            logger.warning("Ferramenta %s falhou: %s: %s", name, type(exc).__name__, exc)
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


registry = ToolRegistry()


# --- Ferramentas genéricas (infra). As do produto entram em arquivos próprios --

class EscalateArgs(ToolArgs):
    reason: str = Field(description="Por que um humano precisa decidir/agir")
    summary: str = Field(description="O que já foi feito e o que falta")
    question: str = Field(description="A pergunta/decisão objetiva para o humano")
    recommendation: str | None = Field(default=None, description="Sua recomendação, se houver")


@registry.tool(
    name=ESCALATE_TOOL,
    description=(
        "Encerra a execução e escala para um humano. Use quando: a decisão é sobre pessoas "
        "(contratar, demitir, salário, avaliação); falta um dado crítico; a instrução é ambígua; "
        "ou as ferramentas falharam repetidamente."
    ),
)
def escalate_to_human(args: EscalateArgs) -> dict:
    # Ponto de integração do human-in-the-loop (Slack, e-mail, fila no Supabase...).
    return {"escalated": True, **args.model_dump()}


class CurrentTimeArgs(ToolArgs):
    timezone: str = Field(default="America/Recife", description="Fuso IANA, ex.: America/Sao_Paulo")


@registry.tool(description="Retorna data e hora atuais em um fuso horário. Use para calcular prazos.")
def get_current_time(args: CurrentTimeArgs) -> dict:
    now = datetime.now(ZoneInfo(args.timezone))
    return {"iso": now.isoformat(), "weekday": now.strftime("%A")}
