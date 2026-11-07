"""Configuração centralizada, lida do .env (pydantic-settings)."""

import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM (Featherless)
    featherless_api_key: str = ""
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str = "zai-org/GLM-5.2"
    featherless_model_fast: str = ""
    featherless_model_fallback: str = ""
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 3
    agent_max_steps: int = 8

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Langfuse (o SDK também lê estas variáveis direto do ambiente)
    langfuse_enabled: bool = True          # interruptor: false desliga o tracing sem mexer no código
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"   # nome antigo (deprecated no SDK)
    langfuse_base_url: str = ""                          # nome atual; tem prioridade

    # Busca de preços (Fatia B): várias chaves Tavily separadas por vírgula (1 conta por integrante)
    tavily_api_keys: str = ""
    pesquisa_concorrencia_llm: int = 3     # "porteiro": chamadas simultâneas à Featherless (medido: 6 simultâneas ao Qwen3-32B → 3 respostas vazias)
    pesquisa_concorrencia_busca: int = 8   # buscas simultâneas no Tavily/DuckDuckGo
    pesquisa_max_lojas: int = 5
    pesquisa_cache_dias: int = 7
    pesquisa_modelo_extracao: str = "Qwen/Qwen3-32B"  # rápido; o GLM-5.2 fica para o agente que refaz
    pesquisa_modelo_agente: str = ""        # vazio = FEATHERLESS_MODEL (GLM-5.2)
    pesquisa_min_lojas: int = 2             # menos que isso → o agente refaz a busca
    pesquisa_max_refazer: int = 2           # buscas extras que o agente pode fazer por item
    pesquisa_timeout_agente_s: float = 40   # o agente não segura o orçamento inteiro (medido: ~20 s por rodada com GLM-5.2)

    @property
    def langfuse_url(self) -> str:
        return self.langfuse_base_url or self.langfuse_host

    @property
    def tavily_keys(self) -> list[str]:
        return [k.strip().strip('"').strip("'") for k in self.tavily_api_keys.split(",") if k.strip().strip('"\'')]

    @property
    def llm_configured(self) -> bool:
        return bool(self.featherless_api_key)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def langfuse_configured(self) -> bool:
        """Chaves reais (pk-lf-<uuid>) têm ~40 caracteres; placeholders do .env.example não."""
        def looks_real(key: str, prefix: str) -> bool:
            return key.startswith(prefix) and len(key) >= 30 and "xxx" not in key and "..." not in key
        return looks_real(self.langfuse_public_key, "pk-lf-") and looks_real(self.langfuse_secret_key, "sk-lf-")

    @property
    def langfuse_active(self) -> bool:
        return self.langfuse_enabled and self.langfuse_configured


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.langfuse_active:
        # O SDK do Langfuse lê do ambiente do processo; o .env só é lido pelo Settings.
        # Exporta para funcionar também fora do Docker/Vercel (ex.: uvicorn ou scripts no notebook).
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_url)
    else:
        # Desliga o SDK por completo (sem 401 em background, sem quebrar a API).
        os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
        logging.getLogger(__name__).warning(
            "Langfuse DESLIGADO (LANGFUSE_ENABLED=false ou chaves ausentes/placeholder). "
            "O agente funciona normalmente, só sem traces."
        )
    return settings


def load_prompt(name: str, **variables: str) -> str:
    """Carrega prompts/<name>.md e substitui placeholders {{CHAVE}}."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in variables.items():
        text = text.replace("{{" + key.upper() + "}}", value)
    return text
