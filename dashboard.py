"""Componentes Streamlit do dashboard de análise."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis_engine import (
    FILTER_FIELDS,
    AnalysisData,
    analysis_workbook,
    apply_filters,
    build_audit,
    calculate_metrics,
    normalize_header,
    prepare_analysis,
)

COLOR = "#3B82F6"
WEEKDAYS = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}


def dataframe_from_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(file_bytes), engine="openpyxl")


def render_dashboard(dataframe: pd.DataFrame, original_name: str) -> None:
    analysis = prepare_analysis(dataframe)
    for warning in analysis.warnings:
        st.warning(warning)

    st.subheader("Filtros")
    selections = _render_filters(analysis)
    divergence_col, duration_col, top_col = st.columns(3)
    divergence = divergence_col.number_input("Limite GPS x hodômetro (%)", min_value=1, max_value=500, value=20)
    duration = duration_col.number_input("Duração excessiva (horas)", min_value=1.0, max_value=168.0, value=8.0)
    top = top_col.selectbox("Quantidade nos rankings", [5, 10, 20, "Todos"], index=1)

    filtered = apply_filters(analysis, selections)
    audit_all = build_audit(analysis, float(divergence), float(duration))
    audit = audit_all[audit_all["Índice da linha"].isin(filtered.index)].copy()
    metrics = calculate_metrics(analysis, filtered, set(audit_all["Índice da linha"].tolist()))

    if filtered.empty:
        st.info("Nenhum registro corresponde aos filtros selecionados.")
        return

    _render_metrics(metrics)
    routes = analysis.unique_routes(filtered)
    _render_charts(analysis, routes, top)
    _render_audit(audit)
    _render_downloads(analysis, filtered, audit, metrics, original_name)


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
    available = [(key, analysis.columns[key]) for key in FILTER_FIELDS if key in analysis.columns]
    columns = st.columns(3)
    for position, (key, column) in enumerate(available):
        values = sorted(analysis.data[column].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist())
        selections[key] = columns[position % 3].multiselect(labels[key], values, key=f"filter_{key}")
    if st.button("Limpar filtros"):
        for key in FILTER_FIELDS:
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


def _chart(frame: pd.DataFrame, title: str, kind: str = "bar", x: str | None = None, y: str | None = None, color: str | None = None) -> None:
    if frame.empty or (y and frame[y].dropna().empty):
        st.info(f"Dados insuficientes para: {title}.")
        return
    if kind == "line":
        figure = px.line(frame, x=x, y=y, markers=True, title=title, color_discrete_sequence=[COLOR])
    elif kind == "pie":
        figure = px.pie(frame, names=x, values=y, hole=.45, title=title, color_discrete_sequence=px.colors.sequential.Blues_r)
    elif kind == "scatter":
        figure = px.scatter(frame, x=x, y=y, title=title, color=color, color_discrete_sequence=[COLOR], opacity=.72)
    else:
        figure = px.bar(frame, x=x, y=y, title=title, color_discrete_sequence=[COLOR])
    figure.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(figure, use_container_width=True)


def _ranking(routes: pd.DataFrame, category: str, metric: str, label: str, top: object) -> pd.DataFrame:
    frame = routes.dropna(subset=[category]).groupby(category, as_index=False)[metric].agg("count" if metric == category else "sum")
    frame = frame.rename(columns={category: label, metric: "Valor"}).sort_values("Valor", ascending=False)
    return frame if top == "Todos" else frame.head(int(top))


def _render_charts(analysis: AnalysisData, routes: pd.DataFrame, top: object) -> None:
    st.subheader("Visão geral")
    user, unit = analysis.columns.get("usuario"), analysis.columns.get("unidade")
    left, right = st.columns(2)
    with left:
        if user:
            counts = routes.groupby(user, as_index=False).size().rename(columns={user: "Usuário", "size": "Rotas"}).sort_values("Rotas", ascending=False)
            _chart(counts if top == "Todos" else counts.head(int(top)), "Usuários com mais rotas", x="Usuário", y="Rotas")
        else:
            st.info("Coluna de usuário não identificada para o ranking de rotas.")
    with right:
        if user:
            km = routes.groupby(user, as_index=False)["__distancia_gps_valida"].sum().rename(columns={user: "Usuário", "__distancia_gps_valida": "Quilômetros"}).sort_values("Quilômetros", ascending=False)
            _chart(km if top == "Todos" else km.head(int(top)), "Usuários com maior quilometragem", x="Usuário", y="Quilômetros")
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
        _chart(daily, "Quantidade de rotas por dia", "line", "Data", "Rotas")
    with chart_pairs[1]:
        if unit:
            by_unit = routes.groupby(unit, as_index=False)["__distancia_gps_valida"].sum().rename(columns={unit: "Unidade", "__distancia_gps_valida": "Quilômetros"})
            _chart(by_unit.sort_values("Quilômetros", ascending=False), "Quilometragem por unidade", x="Unidade", y="Quilômetros")
        else:
            st.info("Coluna de unidade não identificada.")

    for keys, titles in (("motivo", "Distribuição das rotas por motivo"), ("regiao", "Distribuição das rotas por região")):
        column = analysis.columns.get(keys)
        if column:
            distribution = routes.groupby(column, as_index=False).size().rename(columns={column: "Categoria", "size": "Rotas"})
            _chart(distribution, titles, "pie", "Categoria", "Rotas")
        else:
            st.info(f"Coluna de {keys.replace('_', ' ')} não identificada.")

    temporal = st.columns(2)
    with temporal[0]:
        weekdays = dated.groupby("Dia da semana", as_index=False).size().rename(columns={"size": "Rotas"}) if not dated.empty else pd.DataFrame()
        _chart(weekdays, "Rotas por dia da semana", x="Dia da semana", y="Rotas")
    with temporal[1]:
        hourly = dated.groupby("Hora", as_index=False).size().rename(columns={"size": "Rotas"}) if not dated.empty else pd.DataFrame()
        _chart(hourly, "Rotas por horário de início", x="Hora", y="Rotas")

    comparison = routes.dropna(subset=["__distancia_gps_valida", "__distancia_hodometro"]).copy()
    _chart(comparison, "Distância GPS x hodômetro", "scatter", "__distancia_gps_valida", "__distancia_hodometro")


def _render_audit(audit: pd.DataFrame) -> None:
    st.subheader("Auditoria dos dados")
    if audit.empty:
        st.success("Nenhuma inconsistência foi identificada com os limites atuais.")
        return
    visible = audit.drop(columns=["Índice da linha"], errors="ignore")
    st.dataframe(visible, use_container_width=True, hide_index=True)
    st.download_button("Baixar inconsistências em CSV", visible.to_csv(index=False).encode("utf-8-sig"), "inconsistencias.csv", "text/csv")


def _render_downloads(analysis: AnalysisData, filtered: pd.DataFrame, audit: pd.DataFrame, metrics: dict[str, object], original_name: str) -> None:
    st.subheader("Downloads da análise")
    public_columns = [column for column in filtered.columns if not str(column).startswith("__")]
    stem = original_name.rsplit(".", 1)[0]
    left, right = st.columns(2)
    left.download_button(
        "Baixar dados filtrados em CSV",
        filtered[public_columns].to_csv(index=False).encode("utf-8-sig"),
        f"{stem}_dados_filtrados.csv",
        "text/csv",
        use_container_width=True,
    )
    right.download_button(
        "Baixar resumo em Excel",
        analysis_workbook(metrics, filtered, audit, analysis),
        f"{stem}_resumo_analise.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
