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
    langfuse_host: str = "https://cloud.langfuse.com"

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
    if not settings.langfuse_active:
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
