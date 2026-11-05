"""Loop base de agente com tool calling (OpenAI-compatible -> Featherless).

- `langfuse.openai.OpenAI` é drop-in do SDK da OpenAI: cada chamada ao LLM vira
  uma generation no Langfuse (tokens, custo, latência) sem código extra.
- `@observe` agrupa a execução inteira (LLM + ferramentas) em um único trace.
- Retry/backoff em 429/5xx fica a cargo do próprio SDK (`max_retries`).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal

from langfuse import get_client, observe
from langfuse.openai import OpenAI
from pydantic import BaseModel, Field

from .config import get_settings, load_prompt
from .tools import ToolRegistry, registry

logger = logging.getLogger(__name__)


class AgentStep(BaseModel):
    tool: str
    arguments: Any
    result: dict


class AgentResult(BaseModel):
    status: Literal["completed", "max_steps_reached", "error"]
    output: str | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    trace_id: str | None = None


def build_llm_client() -> OpenAI:
    s = get_settings()
    return OpenAI(
        api_key=s.featherless_api_key,
        base_url=s.featherless_base_url,
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
    )


class Agent:
    def __init__(
        self,
        system_prompt: str | None = None,
        tools: ToolRegistry = registry,
        model: str | None = None,
        max_steps: int | None = None,
        client: OpenAI | None = None,
    ) -> None:
        s = get_settings()
        self.system_prompt = system_prompt or load_prompt("system_prompt")
        self.tools = tools
        self.model = model or s.featherless_model
        self.max_steps = max_steps or s.agent_max_steps
        self.temperature = s.llm_temperature
        self.client = client or build_llm_client()

    @observe(name="agent.run")
    def run(self, task: str, context: dict | None = None) -> AgentResult:
        started = time.perf_counter()
        user_content = task if not context else f"{task}\n\nContexto:\n{json.dumps(context, ensure_ascii=False)}"
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]
        result = AgentResult(status="max_steps_reached", model=self.model)

        try:
            for _ in range(self.max_steps):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tools.schemas() or None,
                    temperature=self.temperature,
                )
                if response.usage:
                    result.prompt_tokens += response.usage.prompt_tokens or 0
                    result.completion_tokens += response.usage.completion_tokens or 0

                message = response.choices[0].message
                messages.append(message.model_dump(exclude_none=True))

                if not message.tool_calls:
                    result.status = "completed"
                    result.output = message.content
                    break

                for call in message.tool_calls:
                    tool_result = self.tools.execute(call.function.name, call.function.arguments)
                    result.steps.append(
                        AgentStep(tool=call.function.name, arguments=call.function.arguments, result=tool_result)
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                        }
                    )
        except Exception as exc:  # noqa: BLE001 — falha do LLM após retries
            logger.exception("Execução do agente falhou")
            result.status = "error"
            result.output = f"{type(exc).__name__}: {exc}"

        result.latency_ms = int((time.perf_counter() - started) * 1000)
        result.trace_id = get_client().get_current_trace_id()
        return result
