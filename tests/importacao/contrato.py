"""Contrato JSON padronizado da importação de quantitativos.

Fonte da verdade: docs/testes/casos-de-teste-importacao.md (seção 1).
Usado para (1) validar os JSON esperados das fixtures e (2) pela API, que
NÃO confia no front: o mesmo modelo valida o corpo de POST na rota de importação.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

UNIDADES = Literal["m", "m2", "m3", "un", "kg", "l", "cm", "mm", "ft-in"]

CODIGOS_ERRO = Literal[
    "ARQUIVO_VAZIO", "FORMATO_INVALIDO", "FORMATO_NAO_SUPORTADO", "ARQUIVO_PROTEGIDO",
    "ARQUIVO_CORROMPIDO", "ARQUIVO_GRANDE_DEMAIS", "CSV_MALFORMADO", "CABECALHO_NAO_ENCONTRADO",
]
CODIGOS_AVISO = Literal[
    "SEM_DADOS", "COLUNAS_EXTRAS", "COLUNAS_FALTANTES", "COLUNA_DUPLICADA", "QUANTIDADE_AUSENTE",
    "VALOR_NAO_NUMERICO", "VALOR_NEGATIVO", "NUMERO_AMBIGUO", "UNIDADES_MISTAS", "UNIDADE_IMPERIAL",
    "ERRO_FORMULA", "TOTAL_DIVERGENTE", "CODIFICACAO_INVALIDA", "TEXTO_TRUNCADO",
    "EXTENSAO_INCORRETA", "CABECALHO_MULTILINHA",
]


class Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Origem(Estrito):
    arquivo: str
    formato: Literal["csv", "xlsx", "xls", "xlsm", "txt"]
    software: Literal["revit", "sketchup", "desconhecido"] = "desconhecido"
    aba: str | None = None
    delimitador: str | None = None
    codificacao: str | None = None
    linhas_lidas: int = Field(ge=0)
    linhas_descartadas: int = Field(ge=0)


class Item(Estrito):
    linha: int = Field(ge=1)
    categoria: str | None = None
    descricao: str | None = Field(default=None, max_length=2000)
    quantidade: float | None = None      # strict: string "12,5" -> 422 (decisão D7)
    unidade: UNIDADES | None = None
    nivel: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class Aviso(Estrito):
    linha: int | None = None
    codigo: CODIGOS_AVISO
    mensagem: str


class Importacao(Estrito):
    origem: Origem
    itens: list[Item] = Field(max_length=100_000)   # decisão D6
    avisos: list[Aviso] = Field(default_factory=list)


class Erro(Estrito):
    codigo: CODIGOS_ERRO
    mensagem: str
    linha: int | None = None
    colunas_encontradas: list[str] | None = None


class RespostaErro(Estrito):
    erro: Erro
