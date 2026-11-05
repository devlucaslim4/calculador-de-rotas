"""Contratos Pydantic expostos para o Copilot Studio."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

FilterValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class FiltrosAnalise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: list[FilterValue] = Field(
        default_factory=list, max_length=100, description="Nomes exatos de usuários."
    )
    unidade: list[FilterValue] = Field(
        default_factory=list, max_length=100, description="Nomes exatos de unidades."
    )
    regiao: list[FilterValue] = Field(
        default_factory=list, max_length=100, description="Nomes exatos de regiões."
    )
    motivo: list[FilterValue] = Field(
        default_factory=list, max_length=100, description="Motivos exatos do deslocamento."
    )
    centro_custo: list[FilterValue] = Field(
        default_factory=list, max_length=100, description="Centros de custo exatos."
    )
    status: list[FilterValue] = Field(
        default_factory=list, max_length=100, description="Status exatos das rotas."
    )
    data_inicio: date | None = Field(
        default=None,
        description="Primeira data de início da rota incluída, no formato AAAA-MM-DD.",
    )
    data_fim: date | None = Field(
        default=None,
        description="Última data de início da rota incluída, no formato AAAA-MM-DD.",
    )

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.data_inicio and self.data_fim and self.data_inicio > self.data_fim:
            raise ValueError("data_inicio não pode ser posterior a data_fim")
        return self


class ProcessarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ano: int = Field(ge=2015, le=2100, description="Ano de conclusão dos checklists.")
    mes: int = Field(ge=1, le=12, description="Mês de conclusão, de 1 a 12.")
    filtros: FiltrosAnalise = Field(
        default_factory=FiltrosAnalise,
        description="Filtros opcionais aplicados somente ao resumo e à prévia.",
    )
    limite_previa: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Quantidade máxima de linhas reais devolvidas no JSON.",
    )

    @model_validator(mode="after")
    def validate_filter_period(self) -> Self:
        month_start = date(self.ano, self.mes, 1)
        month_end = date(self.ano, self.mes, monthrange(self.ano, self.mes)[1])
        for field in ("data_inicio", "data_fim"):
            value = getattr(self.filtros, field)
            if value is not None and not month_start <= value <= month_end:
                raise ValueError(f"{field} deve pertencer ao mês e ano consultados")
        return self


class Periodo(BaseModel):
    ano: int
    mes: int


class Contagens(BaseModel):
    encontrados: int
    validos_para_rota: int
    inconsistentes: int
    duplicados_consolidados: int
    rotas_calculadas: int
    rotas_nao_calculadas: int


class ArquivoTemporario(BaseModel):
    id: str
    nome: str
    url_download: str
    expira_em: str


class ProcessarResponse(BaseModel):
    status: str
    mensagem: str
    periodo: Periodo
    contagens: Contagens
    indicadores: dict[str, Any]
    previa: list[dict[str, Any]]
    avisos: list[str]
    arquivo: ArquivoTemporario | None = None


class GerarPlanilhaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arquivo_id: str = Field(
        min_length=36,
        max_length=36,
        description="ID devolvido anteriormente por POST /api/processar.",
    )


class GerarPlanilhaResponse(BaseModel):
    mensagem: str
    arquivo: ArquivoTemporario


class HealthResponse(BaseModel):
    status: str
    servico: str
    versao: str
    configurado: bool


class OpcoesResponse(BaseModel):
    operacoes: list[str]
    meses: list[dict[str, Any]]
    filtros_suportados: list[str]
    categoria: int
    fuso_horario: str
    limite_previa: int
    validade_link_segundos: int


class ErroResponse(BaseModel):
    erro: str
    mensagem: str
    detalhes: list[dict[str, Any]] | None = None
