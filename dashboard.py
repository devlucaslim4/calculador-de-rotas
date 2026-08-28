"""Componentes Streamlit do dashboard de análise."""

from __future__ import annotations

import logging
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis_engine import (
    AnalysisData,
    analysis_workbook,
    apply_filters,
    build_audit,
    calculate_metrics,
    normalize_header,
    prepare_analysis,
)
from report_export import analysis_pdf

COLOR = "#F4511E"
WEEKDAYS = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}
DASHBOARD_FILTER_FIELDS = ("usuario", "unidade", "regiao", "motivo", "centro_custo", "status")


def dataframe_from_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(file_bytes), engine="openpyxl")


def render_dashboard(dataframe: pd.DataFrame, original_name: str, light_mode: bool = False) -> None:
    analysis = prepare_analysis(dataframe)
    for warning in analysis.warnings:
        st.warning(warning)

    st.subheader("Filtros")
    selections = _render_filters(analysis)

    filtered = apply_filters(analysis, selections)
    audit_all = build_audit(analysis, divergence_limit=20, duration_limit=8)
    audit = audit_all[audit_all["Índice da linha"].isin(filtered.index)].copy()
    metrics = calculate_metrics(analysis, filtered, set(audit_all["Índice da linha"].tolist()))

    if filtered.empty:
        st.info("Nenhum registro corresponde aos filtros selecionados.")
        return

    st.caption(f"Exibindo {len(filtered):,.0f} de {len(analysis.data):,.0f} registros".replace(",", "."))
    _render_metrics(metrics)
    routes = analysis.unique_routes(filtered)
    _render_downloads(analysis, filtered, audit, metrics, original_name)
    overview_tab, data_tab, audit_tab = st.tabs(["Visão geral", "Dados detalhados", "Auditoria"])
    with overview_tab:
        _render_charts(analysis, routes, 10, light_mode)
    with data_tab:
        _render_data_table(analysis, filtered)
    with audit_tab:
        _render_audit(audit)


def _render_filters(analysis: AnalysisData) -> dict[str, object]:
    selections: dict[str, object] = {}
    date_values = analysis.data["__data_inicio"].dropna()
    if not date_values.empty:
        minimum, maximum = date_values.min().date(), date_values.max().date()
        selected = st.date_input("Período", value=(minimum, maximum), min_value=minimum, max_value=maximum)
        if isinstance(selected, tuple) and len(selected) == 2:
            selections["periodo"] = selected

    labels = {
        "usuario": "Usuário", "unidade": "Unidade", "regiao": "Região",
        "motivo": "Motivo", "centro_custo": "Centro de custo", "status": "Status",
    }
    available = [(key, analysis.columns[key]) for key in DASHBOARD_FILTER_FIELDS if key in analysis.columns]
    columns = st.columns(3)
    for position, (key, column) in enumerate(available):
        values = sorted(analysis.data[column].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist())
        selections[key] = columns[position % 3].multiselect(
            labels[key], values, key=f"filter_{key}", placeholder="Selecione uma ou mais opções"
        )
    if st.button("Limpar filtros"):
        for key in DASHBOARD_FILTER_FIELDS:
            st.session_state.pop(f"filter_{key}", None)
        st.rerun()
    return selections


def _format_metric(label: str, value: object) -> str:
    if value is None or pd.isna(value):
        return "Não disponível"
    if "quilômetro" in label.lower() or "média" in label.lower():
        return f"{float(value):,.2f} km".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(value):,}".replace(",", ".")


def _render_metrics(metrics: dict[str, object]) -> None:
    st.subheader("Indicadores")
    items = list(metrics.items())
    for start in range(0, len(items), 4):
        columns = st.columns(4)
        for column, (label, value) in zip(columns, items[start:start + 4]):
            column.metric(label, _format_metric(label, value))


def _chart(frame: pd.DataFrame, title: str, kind: str = "bar", x: str | None = None, y: str | None = None, color: str | None = None, light_mode: bool = False) -> None:
    if frame.empty or (y and frame[y].dropna().empty):
        st.info(f"Dados insuficientes para: {title}.")
        return
    if kind == "line":
        figure = px.line(frame, x=x, y=y, markers=True, title=title, color_discrete_sequence=[COLOR])
    elif kind == "pie":
        figure = px.pie(frame, names=x, values=y, hole=.55, title=title, color_discrete_sequence=["#F4511E", "#FF8A65", "#303842", "#667085", "#FDBA74"])
    elif kind == "scatter":
        figure = px.scatter(frame, x=x, y=y, title=title, color=color, color_discrete_sequence=[COLOR], opacity=.72)
    else:
        figure = px.bar(frame, x=x, y=y, title=title, color_discrete_sequence=[COLOR])
    figure.update_layout(template="plotly_white" if light_mode else "plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=55, b=10), font=dict(color="#344054"), title_font=dict(size=16, color="#111827"), hoverlabel=dict(bgcolor="#303842", font_color="white"))
    st.plotly_chart(figure, use_container_width=True)


def _ranking(routes: pd.DataFrame, category: str, metric: str, label: str, top: object) -> pd.DataFrame:
    frame = routes.dropna(subset=[category]).groupby(category, as_index=False)[metric].agg("count" if metric == category else "sum")
    frame = frame.rename(columns={category: label, metric: "Valor"}).sort_values("Valor", ascending=False)
    return frame if top == "Todos" else frame.head(int(top))


def _render_charts(analysis: AnalysisData, routes: pd.DataFrame, top: object, light_mode: bool = False) -> None:
    st.subheader("Visão geral")
    user, unit = analysis.columns.get("usuario"), analysis.columns.get("unidade")
    left, right = st.columns(2)
    with left:
        if user:
            counts = routes.groupby(user, as_index=False).size().rename(columns={user: "Usuário", "size": "Rotas"}).sort_values("Rotas", ascending=False)
            _chart(counts if top == "Todos" else counts.head(int(top)), "Pessoas com mais rotas", x="Usuário", y="Rotas", light_mode=light_mode)
        else:
            st.info("Coluna de usuário não identificada para o ranking de rotas.")
    with right:
        if user:
            km = routes.groupby(user, as_index=False)["__distancia_gps_valida"].sum().rename(columns={user: "Usuário", "__distancia_gps_valida": "Quilômetros"}).sort_values("Quilômetros", ascending=False)
            _chart(km if top == "Todos" else km.head(int(top)), "Pessoas com maior quilometragem", x="Usuário", y="Quilômetros", light_mode=light_mode)
        else:
            st.info("Coluna de usuário não identificada para o ranking de quilometragem.")

    dated = routes.dropna(subset=["__data_inicio"]).copy()
    if not dated.empty:
        dated["Data"] = dated["__data_inicio"].dt.date
        dated["Dia da semana"] = dated["__data_inicio"].dt.dayofweek.map(WEEKDAYS)
        dated["Hora"] = dated["__data_inicio"].dt.hour
    chart_pairs = st.columns(2)
    with chart_pairs[0]:
        daily = dated.groupby("Data", as_index=False).size().rename(columns={"size": "Rotas"}) if not dated.empty else pd.DataFrame()
        _chart(daily, "Quantidade de rotas por dia", "line", "Data", "Rotas", light_mode=light_mode)
    with chart_pairs[1]:
        if unit:
            by_unit = routes.groupby(unit, as_index=False)["__distancia_gps_valida"].sum().rename(columns={unit: "Unidade", "__distancia_gps_valida": "Quilômetros"})
            _chart(by_unit.sort_values("Quilômetros", ascending=False), "Quilometragem por unidade", x="Unidade", y="Quilômetros", light_mode=light_mode)
        else:
            st.info("Coluna de unidade não identificada.")

    distributions = st.columns(2)
    for container, (key, title) in zip(distributions, (("motivo", "Distribuição das rotas por motivo"), ("regiao", "Distribuição das rotas por região"))):
        with container:
            column = analysis.columns.get(key)
            if column:
                distribution = routes.groupby(column, as_index=False).size().rename(columns={column: "Categoria", "size": "Rotas"})
                _chart(distribution, title, "pie", "Categoria", "Rotas", light_mode=light_mode)
            else:
                st.info(f"Coluna de {key.replace('_', ' ')} não identificada.")

    temporal = st.columns(2)
    with temporal[0]:
        weekdays = dated.groupby("Dia da semana", as_index=False).size().rename(columns={"size": "Rotas"}) if not dated.empty else pd.DataFrame()
        _chart(weekdays, "Rotas por dia da semana", x="Dia da semana", y="Rotas", light_mode=light_mode)
    with temporal[1]:
        hourly = dated.groupby("Hora", as_index=False).size().rename(columns={"size": "Rotas"}) if not dated.empty else pd.DataFrame()
        _chart(hourly, "Rotas por horário de início", x="Hora", y="Rotas", light_mode=light_mode)

    comparison = routes.dropna(subset=["__distancia_gps_valida", "__distancia_hodometro"]).copy()
    _chart(comparison, "Distância GPS x hodômetro", "scatter", "__distancia_gps_valida", "__distancia_hodometro", light_mode=light_mode)


def _render_data_table(analysis: AnalysisData, filtered: pd.DataFrame) -> None:
    st.subheader("Dados das rotas")
    st.caption("Consulte os registros que correspondem aos filtros aplicados acima.")
    preferred = ["usuario", "unidade", "regiao", "motivo", "status", "data_inicio", "data_fim", "distancia_gps"]
    columns = [analysis.columns[key] for key in preferred if key in analysis.columns]
    if not columns:
        columns = [column for column in filtered.columns if not str(column).startswith("__")]
    visible = filtered[columns].copy()
    labels = {
        analysis.columns.get("usuario"): "Nome",
        analysis.columns.get("unidade"): "Unidade",
        analysis.columns.get("regiao"): "Região",
        analysis.columns.get("motivo"): "Motivo",
        analysis.columns.get("status"): "Status",
        analysis.columns.get("data_inicio"): "Início",
        analysis.columns.get("data_fim"): "Fim",
        analysis.columns.get("distancia_gps"): "Distância GPS (km)",
    }
    visible = visible.rename(columns={key: value for key, value in labels.items() if key})
    st.dataframe(visible, use_container_width=True, hide_index=True, height=460)


def _render_audit(audit: pd.DataFrame) -> None:
    st.subheader("Auditoria dos dados")
    if audit.empty:
        st.success("Nenhuma inconsistência foi identificada com os limites atuais.")
        return
    visible = audit.drop(columns=["Índice da linha"], errors="ignore")
    st.dataframe(visible, use_container_width=True, hide_index=True)
    st.download_button("Baixar inconsistências em CSV", visible.to_csv(index=False).encode("utf-8-sig"), "inconsistencias.csv", "text/csv")


def _render_downloads(analysis: AnalysisData, filtered: pd.DataFrame, audit: pd.DataFrame, metrics: dict[str, object], original_name: str) -> None:
    st.subheader("Baixar análise")
    st.caption("Os arquivos abaixo respeitam todos os filtros selecionados.")
    public_columns = [column for column in filtered.columns if not str(column).startswith("__")]
    stem = original_name.rsplit(".", 1)[0]
    left, middle, right = st.columns(3)
    left.download_button(
        "Baixar dados filtrados em CSV",
        filtered[public_columns].to_csv(index=False).encode("utf-8-sig"),
        f"{stem}_dados_filtrados.csv",
        "text/csv",
        use_container_width=True,
    )
    try:
        pdf_data = analysis_pdf(metrics, filtered, audit, analysis, original_name)
        middle.download_button(
            "Baixar relatório em PDF",
            pdf_data,
            f"{stem}_relatorio_analise.pdf",
            "application/pdf",
            use_container_width=True,
        )
    except Exception:
        logging.exception("Falha ao gerar o relatório PDF")
        middle.error("Não foi possível preparar o PDF.")
    try:
        excel_data = analysis_workbook(metrics, filtered, audit, analysis)
        right.download_button(
            "Baixar relatório em Excel",
            excel_data,
            f"{stem}_resumo_analise.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        logging.exception("Falha ao gerar o relatório Excel")
        right.error("Não foi possível preparar o Excel.")
