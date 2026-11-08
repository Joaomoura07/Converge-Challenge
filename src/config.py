"""Configuração centralizada, lida do .env (pydantic-settings)."""

import logging
import os
from functools import lru_cache
from pathlib import Path
from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM (Featherless)
    featherless_api_key: str = Field(default="", repr=False)  # nome antigo (1 chave); continua aceito
    featherless_api_keys: str = Field(default="", repr=False)  # várias chaves separadas por vírgula
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str = "zai-org/GLM-5.2"
    featherless_model_fast: str = ""
    featherless_model_fallback: str = ""
    llm_temperature: float = 0.0   # extração de preço e agente de busca: determinístico (sem criatividade)
    llm_top_p: float = 0.1         # junto com temperature=0: só os tokens mais prováveis
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 3
    agent_max_steps: int = 8
    # POST /agent/run (agente genérico do template, sem uso no site): desligado por padrão para ninguém gastar os
    # créditos da Featherless pelo link público. AGENT_RUN_ATIVO=true no .env local para usar nos testes manuais.
    agent_run_ativo: bool = False

    # Supabase
    supabase_url: str = ""
    supabase_key: str = Field(default="", repr=False)

    # Langfuse (o SDK também lê estas variáveis direto do ambiente)
    langfuse_enabled: bool = True          # interruptor: false desliga o tracing sem mexer no código
    langfuse_public_key: str = ""
    langfuse_secret_key: str = Field(default="", repr=False)
    langfuse_host: str = "https://cloud.langfuse.com"   # nome antigo (deprecated no SDK)
    langfuse_base_url: str = ""                          # nome atual; tem prioridade

    # Busca de preços (Fatia B): várias chaves Tavily separadas por vírgula (1 conta por integrante)
    tavily_api_keys: str = Field(default="", repr=False)
    # Segunda fonte de preço (Google Shopping via serper.dev) e lojas próximas. Vazio = recurso desligado.
    serper_api_keys: str = Field(default="", repr=False)  # várias chaves em rodízio
    serper_debug_json: bool = False  # diagnóstico temporário do primeiro anúncio do Shopping
    ors_api_key: str = Field(default="", repr=False)  # OpenRouteService: rota até as lojas
    pesquisa_concorrencia_llm: int = 3     # "porteiro": chamadas simultâneas à Featherless (medido: 6 simultâneas ao Qwen3-32B → 3 respostas vazias)
    pesquisa_concorrencia_busca: int = 8   # buscas simultâneas no Tavily/DuckDuckGo
    pesquisa_max_lojas: int = 5             # anúncios da lista fixa de lojas
    pesquisa_busca_aberta: bool = True      # 2ª busca em qualquer loja do Brasil, com a cidade/UF da obra
    pesquisa_max_abertas: int = 4           # anúncios da busca aberta (só os com preço escrito)
    pesquisa_max_anuncios: int = 8          # total que vai para a extração (fixas primeiro)
    pesquisa_prazo_aberta_s: float = 5      # passou disso, o item segue só com a lista fixa (a aberta chegou a 10 s)
    pesquisa_cache_dias: int = 7
    # Extração (o LLM lê os anúncios e confere se é o mesmo produto). Medido em 08/11 com a página da loja como gabarito,
    # 16 itens: Kimi-K2 0 erros em 11 confirmadas, 2,4 s; Qwen3-32B 4 erros em 20 (20%), 3,7 s; DeepSeek-V3.2 2 em 16,
    # 6 s. Custo do Kimi: ~US$ 0,0008 por extração (5x o Qwen; ~US$ 0,05 por orçamento de 20 itens).
    pesquisa_modelo_extracao: str = "moonshotai/Kimi-K2-Instruct-0905"
    # "Pesquisar de novo" com alternativa. Medido em 07/11 (3 casos): Gemma 4–10 s e US$ 0,00007, mantendo cor e
    # acabamento; Qwen3-32B 12–24 s; GLM-5.2 48–125 s (com a busca depois, estourava os 120 s da tela).
    # 08/11: Kimi-K2 em toda a pesquisa. Alternativa: 2–6 s (Gemma até 26 s), com o acabamento conferido no código;
    # agente que refaz a busca: 17 s contra 40 s do Qwen3-32B no mesmo item.
    pesquisa_modelo_alternativa: str = "moonshotai/Kimi-K2-Instruct-0905"
    pesquisa_modelo_agente: str = "moonshotai/Kimi-K2-Instruct-0905"
    pesquisa_paginas_por_rodada: int = Field(default=2, ge=0, le=3)
    pesquisa_pagina_timeout_s: float = Field(default=8, gt=0, le=20)
    pesquisa_max_tokens_saida: int = Field(default=400, ge=100, le=1200)
    pesquisa_hedge_ativo: bool = False
    pesquisa_max_chamadas_item: int = Field(default=6, ge=1, le=12)
    pesquisa_max_tokens_item: int = Field(default=30000, ge=1000)
    pesquisa_max_chamadas_execucao: int = Field(default=120, ge=1)
    pesquisa_max_tokens_execucao: int = Field(default=200000, ge=1000)
    pesquisa_limite_usd_item: float = Field(default=0.03, gt=0)
    pesquisa_limite_usd_execucao: float = Field(default=0.25, gt=0)
    pesquisa_hedge_s: float = 8             # extração sem resposta nesse tempo → reserva em paralelo (outra chave)
    pesquisa_min_lojas: int = 2             # menos que isso → o agente refaz a busca
    pesquisa_max_refazer: int = 2           # buscas extras que o agente pode fazer por item
    pesquisa_timeout_agente_s: float = 40   # o agente não segura o orçamento inteiro (medido: ~20 s por rodada com GLM-5.2)
    # Fase 2 (agente depois do caminho rápido de todos os itens). Medido na etapa 9: com o agente disputando
    # as mesmas vagas das extrações, o 1º item chegava em 33 s e 12 agentes estouravam o tempo sem vaga.
    pesquisa_concorrencia_agente: int = 1   # cota PRÓPRIA de chamadas simultâneas ao GLM do agente
    pesquisa_agentes_simultaneos: int = 2   # itens com agente ao mesmo tempo (um pensa enquanto o outro busca)
    pesquisa_prazo_agentes_s: float = 90    # prazo total da fase 2 (era 60: muitos itens ficavam "sem tempo"; a função tem 300 s)
    # Prazo do orçamento inteiro (fases 1 e 2), abaixo dos 300 s da função: sobra tempo para gravar, concluir e
    # chamar a Fatia C. Item que não termina a tempo vira "erro" com "Pesquisar de novo" (não fica "buscando").
    pesquisa_prazo_total_s: float = 240
    # Itens por envio. Medido em 08/11: 53 itens em ~110 s; 321 itens estouraram o prazo (94 em "erro" por tempo,
    # total R$ 0). Com 80 a conta fica perto de 200 s. A tela usa o mesmo número (LIMITE_ITENS_PESQUISA em tipos.ts).
    pesquisa_max_itens: int = 80
    # Modo gravação de vídeo (rotas /simulacao/...): multiplica as pausas entre os itens reproduzidos. 1 = ~1,5 s
    # entre um item e o próximo; 0 = sem pausa (testes).
    simulacao_ritmo: float = 1.0

    @property
    def langfuse_url(self) -> str:
        return self.langfuse_base_url or self.langfuse_host

    @property
    def serper_keys(self) -> list[str]:
        return [k.strip().strip('"').strip("'") for k in self.serper_api_keys.split(",") if k.strip().strip('"\'')]

    @property
    def tavily_keys(self) -> list[str]:
        return [k.strip().strip('"').strip("'") for k in self.tavily_api_keys.split(",") if k.strip().strip('"\'')]

    @property
    def ors_key(self) -> str:
        return self.ors_api_key.strip().strip('"').strip("'")

    @property
    def featherless_keys(self) -> list[str]:
        """FEATHERLESS_API_KEYS (vírgula, como o Tavily) + FEATHERLESS_API_KEY (nome antigo), sem repetir e sem aspas.
        Quem trocou a variável antiga pela nova no .env/Vercel não quebra nada: as duas valem."""
        brutas = self.featherless_api_keys.split(",") + self.featherless_api_key.split(",")
        limpas = [k.strip().strip('"').strip("'") for k in brutas]
        return list(dict.fromkeys(k for k in limpas if k))

    @property
    def featherless_key(self) -> str:
        """A primeira chave (usada por quem ainda não reparte a carga entre as chaves)."""
        chaves = self.featherless_keys
        return chaves[0] if chaves else ""

    @property
    def llm_configured(self) -> bool:
        return bool(self.featherless_keys)

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
