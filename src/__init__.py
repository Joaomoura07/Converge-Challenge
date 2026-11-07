"""Pacote do backend. Carrega a configuração na importação para exportar as chaves do Langfuse
para o ambiente ANTES de qualquer @observe (senão o SDK inicia sem chave quando um script
importa direto um submódulo, ex.: `from src.busca import buscar`)."""

from .config import get_settings as _get_settings

_get_settings()
