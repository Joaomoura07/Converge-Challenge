"""Loop ReAct com tool calling nativo (OpenAI-compatible -> Featherless).

Ver skills/01-react-agent-pattern.md e skills/03-langfuse-tracing.md.

- Thought      = `message.content` que acompanha os tool_calls (registrado no step)
- Action       = tool_call nativo, argumentos validados por Pydantic
- Observation  = dict {"ok": ..., "result" | "error"} devolvido ao modelo
- Final Answer = mensagem sem tool_calls

Guardas: limite de passos, 3 falhas consecutivas -> escala p/ humano,
modelo reserva em 400 (modelo frio/sem suporte) e 503 (sem capacidade).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal

from langfuse import get_client, observe, propagate_attributes
from openai import APIStatusError, OpenAI
from pydantic import BaseModel, Field

from .config import get_settings, load_prompt
from .tools import ESCALATE_TOOL, ToolRegistry, registry

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3
FALLBACK_STATUS_CODES = {400, 503}


class AgentStep(BaseModel):
    thought: str | None = None
    tool: str
    arguments: Any
    result: dict


class AgentResult(BaseModel):
    status: Literal["completed", "escalated", "max_steps_reached", "error"]
    output: str | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    trace_id: str | None = None
    trace_url: str | None = None


def build_llm_client() -> OpenAI:
    s = get_settings()
    # max_retries: o SDK faz backoff exponencial com jitter em 408/409/429/5xx
    return OpenAI(
        api_key=s.featherless_api_key or "missing",
        base_url=s.featherless_base_url,
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
    )


class Agent:
    def __init__(
        self,
        name: str = "agent",
        system_prompt: str | None = None,
        tools: ToolRegistry = registry,
        model: str | None = None,
        max_steps: int | None = None,
        client: OpenAI | None = None,
    ) -> None:
        s = get_settings()
        self.name = name
        self.system_prompt = system_prompt or load_prompt("system_prompt")
        self.tools = tools
        self.model = model or s.featherless_model
        self.fallback_model = s.featherless_model_fallback or None
        self.max_steps = max_steps or s.agent_max_steps
        self.temperature = s.llm_temperature
        self.client = client or build_llm_client()

    # --- LLM ----------------------------------------------------------------

    @observe(as_type="generation", name="llm.featherless", capture_input=False, capture_output=False)
    def _complete_once(self, model: str, messages: list[dict]):
        lf = get_client()  # com tracing desligado, os update_* abaixo são no-op
        lf.update_current_generation(model=model, input=messages,
                                     model_parameters={"temperature": self.temperature})
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=self.tools.schemas() or None,
            temperature=self.temperature,
        )
        usage = response.usage
        cost = getattr(usage, "cost", None) if usage else None  # Featherless devolve usage.cost (USD)
        lf.update_current_generation(
            output=response.choices[0].message.model_dump(exclude_none=True),
            usage_details={"input": usage.prompt_tokens, "output": usage.completion_tokens} if usage else None,
            cost_details={"total": float(cost)} if cost is not None else None,
        )
        return response

    def _complete(self, messages: list[dict]):
        try:
            return self._complete_once(self.model, messages)
        except APIStatusError as exc:
            if self.fallback_model and exc.status_code in FALLBACK_STATUS_CODES:
                logger.warning("Modelo %s falhou (%s). Usando reserva %s",
                               self.model, exc.status_code, self.fallback_model)
                return self._complete_once(self.fallback_model, messages)
            raise

    # --- Loop ReAct -----------------------------------------------------------

    def run(self, task: str, context: dict | None = None, session_id: str | None = None,
            tags: list[str] | None = None) -> AgentResult:
        with propagate_attributes(trace_name=f"agent.{self.name}", session_id=session_id,
                                  tags=tags or [], metadata={"model": self.model}):
            return self._run(task, context)

    @observe(as_type="agent", name="agent.run")
    def _run(self, task: str, context: dict | None) -> AgentResult:
        started = time.perf_counter()
        user_content = task if not context else (
            f"{task}\n\nContexto:\n{json.dumps(context, ensure_ascii=False)}"
        )
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]
        result = AgentResult(status="max_steps_reached", model=self.model)
        consecutive_failures = 0

        try:
            for _ in range(self.max_steps):
                response = self._complete(messages)
                result.model = response.model or result.model
                if response.usage:
                    result.prompt_tokens += response.usage.prompt_tokens or 0
                    result.completion_tokens += response.usage.completion_tokens or 0
                    result.cost_usd += float(getattr(response.usage, "cost", 0) or 0)

                message = response.choices[0].message
                messages.append(message.model_dump(exclude_none=True))

                if not message.tool_calls:  # Final Answer
                    result.status = "completed"
                    result.output = message.content
                    break

                for call in message.tool_calls:  # Action -> Observation
                    observation = self.tools.execute(call.function.name, call.function.arguments)
                    result.steps.append(AgentStep(thought=message.content, tool=call.function.name,
                                                  arguments=call.function.arguments, result=observation))
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps(observation, ensure_ascii=False, default=str)})

                    if call.function.name == ESCALATE_TOOL and observation.get("ok"):
                        result.status = "escalated"
                        result.output = json.dumps(observation["result"], ensure_ascii=False)
                        break
                    consecutive_failures = 0 if observation.get("ok") else consecutive_failures + 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        result.status = "escalated"
                        result.output = (f"Escalado após {MAX_CONSECUTIVE_FAILURES} falhas consecutivas. "
                                         f"Último erro: {observation.get('error')}")
                        break

                if result.status == "escalated":
                    break
        except Exception as exc:  # noqa: BLE001 — falha do LLM após retries/reserva
            logger.exception("Execução do agente falhou")
            result.status = "error"
            result.output = f"{type(exc).__name__}: {exc}"

        result.latency_ms = int((time.perf_counter() - started) * 1000)
        self._attach_trace(result)
        return result

    @staticmethod
    def _attach_trace(result: AgentResult) -> None:
        """Telemetria nunca derruba a resposta: chave errada/Langfuse fora = segue sem trace."""
        if not get_settings().langfuse_active:
            return
        try:
            lf = get_client()
            result.trace_id = lf.get_current_trace_id()
            result.trace_url = lf.get_trace_url(trace_id=result.trace_id) if result.trace_id else None
            lf.update_current_span(output=result.model_dump(include={"status", "output"}),
                                   level="WARNING" if result.status != "completed" else None)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Langfuse indisponível (%s): resposta enviada sem trace_url. "
                           "Confira LANGFUSE_* no .env ou use LANGFUSE_ENABLED=false.", type(exc).__name__)
