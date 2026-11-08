"""Contrato da Fatia B (pesquisa de preço) com as outras fatias.

Fonte da verdade: docs/FATIAS-DO-TIME.md, seção "Contratos entre fatias".
tests/fatia_b/test_coerencia.py confere automaticamente que estes modelos batem com o documento.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["buscando", "definido", "pendente_especificacao", "nao_encontrado", "erro"]
Confianca = Literal["alta", "media", "baixa"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemEntrada(_Base):
    """Item como a Fatia A entrega (já revisado pelo arquiteto)."""

    id: str
    descricao: str = Field(min_length=1)
    quantidade: float | None = None
    unidade: str | None = None            # m, m2, m3, un, kg, l, cm, mm
    categoria: str | None = None
    classificacao: Literal["definido", "pendente_especificacao"] | None = None  # de classificar_item() (A)


class Fonte(_Base):
    """Uma loja onde o preço foi encontrado. A Fatia C usa `dominio` para casar com `fornecedores`."""

    loja: str
    dominio: str
    url: str
    preco_embalagem: float = Field(gt=0)
    embalagem: str | None = None
    # Como está NO ANÚNCIO (o que a pessoa vê ao clicar no link). `preco_embalagem`/`embalagem` são o mesmo preço
    # convertido para a embalagem de referência do item, para comparar lojas e somar (a Fatia C usa estes).
    # Medido no site em 07/11: a loja vendia o galão de 3,6 L a R$ 69,90 e a tela mostrava R$ 349,50 (o equivalente
    # em 18 L): ao clicar, o preço "não batia".
    preco_anunciado: float | None = Field(default=None, gt=0)
    embalagem_anunciada: str | None = None
    link_verificado: bool = False   # a página da loja confirmou o produto e o preço anunciado
    perto_da_obra: bool = False   # loja da região da obra (Google Maps pelo CEP) ou rede com loja no estado
    distancia_km: float | None = None   # de carro, aproximada, da obra até a loja (só lojas da região)
    endereco: str | None = None         # endereço da loja da região (Google Maps)


class Validacao(_Base):
    """Conferência do preço do item numa segunda fonte. Só informa: o preço e as `fontes` continuam sendo as lojas."""

    status: Literal["confirmado", "divergente_leve", "divergente", "sem_dados"]
    fonte: str = "google_shopping"
    mediana: float | None = None          # mediana da 2ª fonte, já convertida para a embalagem do item
    diferenca_pct: float | None = None    # |nosso - mediana| / mediana, em %
    n: int = 0                            # anúncios comparáveis usados


class ResultadoItem(_Base):
    """O que a Fatia B grava em `orcamento_itens` (a tela e a Fatia C leem daqui)."""

    item_id: str
    status: Status
    produto_normalizado: str | None = None
    imagem_url: str | None = None
    embalagem: str | None = None
    qtd_embalagens: int | None = Field(default=None, ge=0)
    preco_emb_min: float | None = None
    preco_emb_med: float | None = None
    preco_emb_max: float | None = None
    preco_un_min: float | None = None
    preco_un_med: float | None = None
    preco_un_max: float | None = None
    unidade_preco: str | None = None      # unidade do preço por unidade (ex.: "m2"); None se não convertível
    confianca: Confianca | None = None
    estimativa: bool = False              # True = faixa estimada de item genérico
    fontes: list[Fonte] = Field(default_factory=list)
    premissa: str | None = None           # conta usada na compra, ex.: "rendimento ≈ 8 m²/L (tinta, 2 demãos)"; a tela mostra "≈"
    pergunta: str | None = None           # pergunta ao arquiteto quando pendente
    motivo: str | None = None             # por que pendente / não encontrado / erro
    preco_data: datetime | None = None    # quando o preço foi obtido (cache vencido mostra a data)
    iteracoes: int = Field(default=0, ge=0)  # quantas vezes o agente refez a busca
    validacao: Validacao | None = None    # conferência do preço numa 2ª fonte (Google Shopping); nunca troca o preço

    @model_validator(mode="after")
    def _regras(self) -> "ResultadoItem":
        tem_preco = self.preco_emb_med is not None
        # Regra do agente nº 1: nunca preço sem fonte.
        if tem_preco and not self.fontes:
            raise ValueError("preço sem fonte: todo preço precisa de pelo menos 1 loja em `fontes`")
        if self.status == "definido" and not tem_preco:
            raise ValueError("status 'definido' exige preço médio por embalagem")
        if self.status == "pendente_especificacao" and not self.pergunta:
            raise ValueError("item pendente precisa de uma pergunta objetiva ao arquiteto")
        if self.status in ("nao_encontrado", "erro") and not self.motivo:
            raise ValueError(f"status '{self.status}' precisa de `motivo`")
        trio = [self.preco_emb_min, self.preco_emb_med, self.preco_emb_max]
        if all(v is not None for v in trio) and not (trio[0] <= trio[1] <= trio[2]):
            raise ValueError("faixa inválida: precisa ser mín ≤ médio ≤ máx")
        return self
