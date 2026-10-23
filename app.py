"""Interface web do Calculador de Rotas."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from checklist_api import (
    DEFAULT_CATEGORY_ID,
    DEFAULT_TIMEZONE,
    ChecklistApiClient,
    ChecklistApiError,
)
from checklist_transform import (
    ChecklistTransformationError,
    build_standardized_workbook,
    item_catalog_dataframe,
    transformar_checklists_em_planilha,
)
from dashboard import dataframe_from_excel, render_dashboard, render_route_map
from route_processor import SpreadsheetError, output_filename, process_workbook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
st.set_page_config(page_title="Calculador de Rotas", layout="wide")


def _reset_processed_result() -> None:
    for key in (
        "result",
        "result_name",
        "result_download_label",
        "original_df",
        "processed_df",
        "original_name",
    ):
        st.session_state.pop(key, None)


def _checklist_settings() -> tuple[str, int, str, dict[str, object]]:
    try:
        section = st.secrets["checklist_facil"]
    except Exception:
        return "", DEFAULT_CATEGORY_ID, DEFAULT_TIMEZONE, {}
    token = str(section.get("api_token", "")).strip()
    category_id = int(section.get("category_id", DEFAULT_CATEGORY_ID))
    timezone_name = str(section.get("timezone", DEFAULT_TIMEZONE))
    mapping = dict(section.get("items", {}))
    return token, category_id, timezone_name, mapping


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_month_import(
    token: str,
    category_id: int,
    timezone_name: str,
    item_mapping_items: tuple[tuple[str, object], ...],
    year: int,
    month: int,
):
    """Mantém por um minuto uma consulta idêntica, alinhado ao limite da API."""

    client = ChecklistApiClient(token)
    snapshot = client.fetch_month_snapshot(
        year,
        month,
        category_id=category_id,
        timezone_name=timezone_name,
    )
    transformed = transformar_checklists_em_planilha(
        snapshot,
        dict(item_mapping_items),
        timezone_name=timezone_name,
    )
    return snapshot, transformed, build_standardized_workbook(transformed)


@st.cache_data(ttl=3600, show_spinner=False)
def _process_workbook_cached(workbook_bytes: bytes):
    """Evita recalcular as mesmas coordenadas em cliques repetidos."""

    return process_workbook(workbook_bytes)


def _calculate_and_store(
    workbook_bytes: bytes,
    source_name: str,
    *,
    result_name: str | None = None,
    download_label: str = "Baixar planilha processada",
    show_success: bool = True,
    use_cache: bool = False,
) -> bool:
    progress = st.progress(0, text="Validando a planilha…")

    def update_progress(done: int, total: int) -> None:
        progress.progress(done / total, text=f"Calculando rotas: {done} de {total}")

    try:
        original_df = dataframe_from_excel(workbook_bytes)
        with st.spinner("Consultando as distâncias rodoviárias…"):
            if use_cache:
                summary = _process_workbook_cached(workbook_bytes)
                update_progress(summary.total, summary.total)
            else:
                summary = process_workbook(workbook_bytes, update_progress)
        processed_df = dataframe_from_excel(summary.workbook)
        progress.progress(1.0, text="Processamento concluído")
        st.session_state["result"] = summary
        st.session_state["result_name"] = result_name or output_filename(source_name)
        st.session_state["result_download_label"] = download_label
        st.session_state["original_df"] = original_df
        st.session_state["processed_df"] = processed_df
        st.session_state["original_name"] = source_name
        if show_success:
            st.success(
                "Planilha processada com sucesso. Consulte os resultados abaixo ou abra a aba Análise de Dados."
            )
        return True
    except SpreadsheetError as exc:
        progress.empty()
        st.error(str(exc))
        return False
    except Exception:
        logging.exception("Erro inesperado no processamento")
        progress.empty()
        st.error(
            "Não foi possível concluir o processamento. Verifique os dados e tente novamente em alguns instantes."
        )
        return False


def _render_route_preview(preview) -> None:
    """Exibe uma conferência compacta, pesquisável e com links clicáveis."""

    preferred_columns = [
        "ID RESPOSTA",
        "NOME",
        "UNIDADE",
        "COORDENADA GPS INICIAL",
        "COORDENADA GPS FINAL",
        "VALOR ODOMETRO INICIAL",
        "VALOR ODOMETRO FINAL",
        "DISTÂNCIA HODÔMETRO",
        "DISTÂNCIA GPS",
        "PERCENTUAL DIFERENÇA %",
        "STATUS DA ROTA",
        "LINK DA ROTA",
    ]
    visible_columns = [column for column in preferred_columns if column in preview.columns]
    visible = preview[visible_columns].copy() if visible_columns else preview.copy()

    search_col, status_col = st.columns([2, 1])
    search = search_col.text_input(
        "Pesquisar rotas",
        placeholder="Nome, unidade, ID da resposta ou coordenada",
        key="route_preview_search",
    ).strip()
    status_options = ["Todos"]
    if "STATUS DA ROTA" in visible:
        status_options.extend(
            sorted(visible["STATUS DA ROTA"].dropna().astype(str).unique().tolist())
        )
    selected_status = status_col.selectbox(
        "Status da rota",
        status_options,
        key="route_preview_status",
    )

    if search:
        matches = visible.astype("string").fillna("").apply(
            lambda column: column.str.contains(search, case=False, regex=False)
        )
        visible = visible.loc[matches.any(axis=1)]
    if selected_status != "Todos" and "STATUS DA ROTA" in visible:
        visible = visible.loc[visible["STATUS DA ROTA"].astype(str).eq(selected_status)]

    if "PERCENTUAL DIFERENÇA %" in visible:
        visible["PERCENTUAL DIFERENÇA %"] = (
            pd.to_numeric(visible["PERCENTUAL DIFERENÇA %"], errors="coerce") * 100
        )
    column_config = {}
    for column in ("VALOR ODOMETRO INICIAL", "VALOR ODOMETRO FINAL"):
        if column in visible:
            column_config[column] = st.column_config.NumberColumn(format="%.0f")
    for column in ("DISTÂNCIA HODÔMETRO", "DISTÂNCIA GPS"):
        if column in visible:
            column_config[column] = st.column_config.NumberColumn(format="%.2f km")
    if "PERCENTUAL DIFERENÇA %" in visible:
        column_config["PERCENTUAL DIFERENÇA %"] = st.column_config.NumberColumn(format="%.2f%%")
    if "LINK DA ROTA" in visible:
        column_config["LINK DA ROTA"] = st.column_config.LinkColumn(display_text="Abrir rota")

    st.caption(f"Exibindo {len(visible)} rota(s). Use a busca ou o filtro para conferir os resultados.")
    st.dataframe(
        visible.head(500),
        width="stretch",
        height=520,
        hide_index=True,
        column_config=column_config,
    )


light_mode = bool(st.session_state.get("light_mode", False))

st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at 35% -10%, #172554 0%, #080b13 34%, #040507 78%); }
    [data-testid="stHeader"] { background: rgba(4,5,7,.82); backdrop-filter: blur(18px); }
    [data-testid="stSidebar"] { background: #080b12; border-right: 1px solid #1d2636; }
    [data-testid="stFileUploaderDropzone"] { background: #0c1017; border-color: #242b38; }
    .block-container { max-width: 1320px; padding-top: 2rem; padding-bottom: 5rem; }
    [data-testid="stFileUploader"], [data-testid="stAlert"], div[data-testid="stMetric"] {
        background: rgba(12,16,24,.88); border: 1px solid #202a3a; border-radius: 18px;
        padding: 1rem; box-shadow: 0 14px 36px rgba(0,0,0,.20);
    }
    div[data-testid="stMetric"] { transition: transform .18s ease, border-color .18s ease; }
    div[data-testid="stMetric"]:hover { transform: translateY(-2px); border-color: #3b82f6; }
    h1, h2, h3 { letter-spacing: -.035em; }
    .subtitle { color: #aeb8c8; font-size: 1.05rem; line-height: 1.65; max-width: 760px; margin-bottom: 1.8rem; }
    .file-name { color: #cbd5e1; background: #0b0e14; border: 1px solid #202633; padding: .7rem 1rem; border-radius: 12px; margin: .5rem 0 1rem; }
    .requirements { margin-top: 2rem; padding: 1.25rem 1.4rem; border: 1px solid #202633; border-radius: 16px; background: #090c11; color: #aeb8c8; }
    .requirements code { color: #93c5fd; }
    .stButton > button, .stDownloadButton > button { border-radius: 12px; min-height: 3rem; font-weight: 700; }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        border: 0; color: white; background: linear-gradient(110deg, #2563eb, #4f46e5 60%, #7c3aed);
        box-shadow: 0 10px 28px rgba(37,99,235,.28);
    }
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
        filter: brightness(1.08); transform: translateY(-1px);
    }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .5rem; }
    [data-testid="stTabs"] button { border-radius: 12px; padding-left: 1.2rem; padding-right: 1.2rem; }
    [data-testid="stDataFrame"] { border: 1px solid #202a3a; border-radius: 16px; overflow: hidden; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color: #202a3a; border-radius: 20px; }
    .hero-shell {
        position: relative; overflow: hidden; padding: 1.35rem 1.6rem; margin-bottom: 1rem;
        border: 1px solid #27344a; border-radius: 24px;
        background: linear-gradient(125deg, rgba(15,23,42,.96), rgba(17,24,39,.84) 55%, rgba(30,27,75,.82));
        box-shadow: 0 24px 60px rgba(0,0,0,.28);
    }
    .hero-shell:after {
        content: ""; position: absolute; width: 340px; height: 340px; right: -120px; top: -180px;
        border-radius: 50%; background: radial-gradient(circle, rgba(96,165,250,.26), rgba(79,70,229,0) 68%);
    }
    .hero-kicker { color: #93c5fd; font-size: .78rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
    .hero-copy { color: #b7c4d8; font-size: 1rem; line-height: 1.55; max-width: 700px; margin-top: .45rem; }
    .sidebar-brand { padding: .45rem 0 1rem; }
    .sidebar-brand strong { display: block; color: #f8fafc; font-size: 1.12rem; }
    .sidebar-brand span { color: #8290a6; font-size: .86rem; }
    .flow-step { display: flex; align-items: center; gap: .7rem; padding: .65rem .1rem; color: #8290a6; font-size: .9rem; }
    .flow-dot { width: 1.65rem; height: 1.65rem; flex: 0 0 1.65rem; display: grid; place-items: center; border: 1px solid #334155; border-radius: 50%; font-weight: 800; font-size: .75rem; }
    .flow-step.done { color: #bfdbfe; }
    .flow-step.done .flow-dot { color: white; border-color: #3b82f6; background: #2563eb; }
    .section-intro { color: #8fa0b7; margin: -.3rem 0 1rem; }
    .eyebrow { color: #60a5fa; font-size: .78rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; margin-top: .4rem; }
    .result-callout { padding: 1.1rem 1.2rem; margin: .5rem 0 1rem; border-radius: 16px; border: 1px solid rgba(52,211,153,.32); background: rgba(6,78,59,.14); color: #d1fae5; }
    [data-testid="stSegmentedControl"] { margin-bottom: .75rem; }
    [data-testid="stSegmentedControl"] button { min-height: 2.8rem; }
    button[data-testid="stBaseButton-segmented_controlActive"] {
        color: #bfdbfe; border-color: #3b82f6; background: rgba(37,99,235,.16);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if light_mode:
    st.markdown(
        """
        <style>
        .stApp { background: #f4f7fb; color: #172033; }
        [data-testid="stHeader"] { background: #f4f7fb; border-bottom: 1px solid #d7e0ec; }
        [data-testid="stSidebar"] { background: #ffffff; border-right-color: #d7e0ec; }
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 { color: #172033; }
        .subtitle { color: #526175; }
        [data-testid="stFileUploader"], [data-testid="stAlert"], div[data-testid="stMetric"],
        .requirements { background: rgba(255,255,255,.96); border-color: #d7e0ec; color: #526175; }
        .file-name { color: #26364c; background: #ffffff; border-color: #d7e0ec; }
        [data-baseweb="select"] > div, [data-baseweb="input"] > div,
        [data-baseweb="base-input"], [data-baseweb="popover"] > div {
            background: #ffffff !important; color: #172033 !important; border-color: #aebdd0 !important;
        }
        [data-baseweb="select"] input, [data-baseweb="input"] input,
        [data-baseweb="select"] span { color: #172033 !important; }
        [data-baseweb="select"] svg, [data-baseweb="input"] svg { fill: #334155 !important; }
        .stButton > button, .stDownloadButton > button {
            background: #ffffff; color: #172033; border: 1px solid #9fb0c5;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            color: #1d4ed8; border-color: #2563eb; background: #eff6ff;
        }
        [data-testid="stDataFrame"] { border: 1px solid #cbd5e1; border-radius: 12px; }
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: #172033; }
        [data-testid="stCaptionContainer"] p { color: #526175 !important; }
        [data-testid="stFileUploaderDropzone"] { background: #ffffff; border-color: #aebdd0; }
        [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stFileUploaderDropzone"] small { color: #334155 !important; }
        [data-testid="stFileUploaderDropzone"] svg { color: #2563eb; fill: #2563eb; }
        [data-testid="stFileUploaderDropzone"] button {
            background: #2563eb !important; color: #ffffff !important; border-color: #2563eb !important;
        }
        [data-testid="stFileUploaderDropzone"] button * { color: #ffffff !important; }
        button[data-testid="stBaseButton-segmented_control"] {
            background: #ffffff !important; color: #172033 !important; border-color: #aebdd0 !important;
        }
        button[data-testid="stBaseButton-segmented_controlActive"] {
            background: #2563eb !important; color: #ffffff !important; border-color: #2563eb !important;
        }
        button[data-testid="stBaseButton-segmented_controlActive"] * { color: #ffffff !important; }
        .hero-shell { background: linear-gradient(125deg, #ffffff, #f5f8ff 60%, #eef2ff); border-color: #c9d7eb; box-shadow: 0 20px 50px rgba(30,64,175,.10); }
        .sidebar-brand strong { color: #172033; }
        .hero-copy, .sidebar-brand span, .section-intro, .flow-step { color: #526175; }
        .flow-step.done { color: #1d4ed8; }
        .result-callout { color: #065f46; background: #ecfdf5; border-color: #a7f3d0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="hero-shell">
      <div class="hero-main">
        <div class="hero-kicker">Controle de quilometragem</div>
        <div class="hero-copy">Importe os checklists, calcule distâncias GPS, compare com o hodômetro e baixe uma planilha pronta para conferência.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand"><strong>Calculador de Rotas</strong><span>Checklist Fácil para Excel tratado</span></div>',
        unsafe_allow_html=True,
    )
    st.toggle("Tema claro", key="light_mode", help="Alterna a aparência da aplicação")
    st.divider()
    st.caption("FLUXO")
    imported = "api_import" in st.session_state or "upload_token" in st.session_state
    calculated = "result" in st.session_state
    st.markdown(
        f"""
        <div class="flow-step done"><span class="flow-dot">1</span><span>Escolher a origem</span></div>
        <div class="flow-step {'done' if imported else ''}"><span class="flow-dot">2</span><span>Importar os dados</span></div>
        <div class="flow-step {'done' if calculated else ''}"><span class="flow-dot">3</span><span>Calcular as rotas</span></div>
        <div class="flow-step {'done' if calculated else ''}"><span class="flow-dot">4</span><span>Baixar o Excel</span></div>
        """,
        unsafe_allow_html=True,
    )

route_tab, map_tab, analysis_tab = st.tabs(["Calcular Rotas", "Mapa 3D", "Análise de Dados"])

with route_tab:
    st.markdown('<div class="eyebrow">Etapa 1</div>', unsafe_allow_html=True)
    st.subheader("Escolha como deseja começar")
    st.markdown(
        '<div class="section-intro">Importe direto do Checklist Fácil ou processe uma planilha que você já possui.</div>',
        unsafe_allow_html=True,
    )
    source = st.segmented_control(
        "Origem dos dados",
        ("Importar do Checklist Fácil", "Enviar planilha Excel"),
        default="Importar do Checklist Fácil",
        width="stretch",
        label_visibility="collapsed",
    )
    if st.session_state.get("last_source") != source:
        _reset_processed_result()
        st.session_state["last_source"] = source

    if source == "Enviar planilha Excel":
        uploaded_file = st.file_uploader("Envie uma planilha Excel (.xlsx)", type=["xlsx"], max_upload_size=25)

        if uploaded_file is not None:
            upload_token = (uploaded_file.name, uploaded_file.size)
            if st.session_state.get("upload_token") != upload_token:
                _reset_processed_result()
                st.session_state["upload_token"] = upload_token

            st.markdown(f'<div class="file-name">{uploaded_file.name}</div>', unsafe_allow_html=True)

            if st.button(
                "Calcular rotas e gerar Excel",
                type="primary",
                width="stretch",
            ):
                if not uploaded_file.name.lower().endswith(".xlsx"):
                    st.error("Envie um arquivo no formato .xlsx.")
                else:
                    _calculate_and_store(uploaded_file.getvalue(), uploaded_file.name)
    else:
        token, category_id, timezone_name, item_mapping = _checklist_settings()
        try:
            now = datetime.now(ZoneInfo(timezone_name))
        except Exception:
            timezone_name = DEFAULT_TIMEZONE
            now = datetime.now(ZoneInfo(timezone_name))

        st.markdown('<div class="eyebrow">Etapa 2</div>', unsafe_allow_html=True)
        st.subheader("Defina o período da consulta")
        st.markdown(
            '<div class="section-intro">Buscaremos somente os checklists concluídos e calcularemos todas as rotas válidas em lote.</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns(2)
        month_names = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
            7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
        }
        selected_month = left.selectbox(
            "Mês de conclusão",
            options=list(month_names),
            index=now.month - 1,
            format_func=month_names.get,
        )
        selected_year = int(
            right.number_input("Ano de conclusão", min_value=2015, max_value=now.year + 1, value=now.year, step=1)
        )
        st.caption(
            f"Categoria {category_id} • período interpretado em {timezone_name} • somente status concluído"
        )
        if not token:
            st.info(
                "Configure a chave da API em `.streamlit/secrets.toml` para habilitar a consulta. "
                "O arquivo de exemplo mostra todos os campos necessários."
            )

        if st.button(
            "Importar, calcular e gerar Excel",
            type="primary",
            width="stretch",
        ):
            st.session_state.pop("api_import", None)
            _reset_processed_result()
            try:
                with st.spinner("Consultando avaliações, respostas e cadastros da API…"):
                    snapshot, transformed, standardized = _fetch_month_import(
                        token,
                        category_id,
                        timezone_name,
                        tuple(sorted(item_mapping.items())),
                        selected_year,
                        selected_month,
                    )
                st.session_state["api_import"] = {
                    "year": selected_year,
                    "month": selected_month,
                    "snapshot": snapshot,
                    "transformed": transformed,
                    "workbook": standardized,
                    "filename": f"checklists_{selected_year}_{selected_month:02d}.xlsx",
                }
                if transformed.valid:
                    treated_name = f"checklists_{selected_year}_{selected_month:02d}_tratada.xlsx"
                    calculated = _calculate_and_store(
                        standardized,
                        st.session_state["api_import"]["filename"],
                        result_name=treated_name,
                        download_label="Baixar planilha com rotas calculadas",
                        show_success=False,
                        use_cache=True,
                    )
                    if calculated:
                        result = st.session_state["result"]
                        if result.failed:
                            st.warning(
                                f"Importação concluída: {result.calculated} rota(s) calculada(s) e "
                                f"{result.failed} não calculada(s). Consulte a coluna STATUS DA ROTA."
                            )
                        else:
                            st.success(
                                f"Importação concluída. As {result.calculated} rotas foram calculadas "
                                "e incluídas na planilha final."
                            )
                else:
                    st.warning(
                        "A consulta foi concluída, mas nenhum registro possui as duas coordenadas "
                        "válidas para calcular a rota."
                    )
            except (ChecklistApiError, ChecklistTransformationError) as exc:
                st.error(str(exc))
            except Exception:
                logging.exception("Erro inesperado ao importar checklists")
                st.error("Não foi possível concluir a importação. Nenhum arquivo parcial foi gerado.")

        api_import = st.session_state.get("api_import")
        if api_import:
            transformed = api_import["transformed"]
            metric_columns = st.columns(4)
            metric_columns[0].metric("Checklists encontrados", transformed.found)
            metric_columns[1].metric("Com coordenadas para rota", transformed.valid)
            metric_columns[2].metric("Sem coordenadas válidas", transformed.inconsistent)
            coverage = (transformed.valid / transformed.found * 100) if transformed.found else 0
            metric_columns[3].metric("Cobertura dos dados", f"{coverage:.1f}%")
            if transformed.duplicate_count:
                st.caption(
                    f"{transformed.duplicate_count} registro(s) duplicado(s) foram consolidados pelo ID da resposta."
                )
            for warning in transformed.mapping_warnings:
                st.warning(warning)

            with st.expander("Configuração avançada: itens e mapeamento utilizado"):
                st.dataframe(item_catalog_dataframe(api_import["snapshot"]), width="stretch", hide_index=True)
                st.json(transformed.resolved_mapping)

            preview = st.session_state.get("processed_df")
            preview_title = "Prévia da planilha com rotas calculadas"
            if preview is None:
                preview = transformed.valid_rows if not transformed.valid_rows.empty else transformed.all_rows
                preview_title = "Prévia dos dados importados"
            st.subheader(preview_title)
            _render_route_preview(preview)
            if transformed.inconsistent:
                with st.expander("Ver registros sem coordenadas válidas"):
                    st.dataframe(transformed.inconsistent_rows, width="stretch", hide_index=True)

    if "result" in st.session_state:
        result = st.session_state["result"]
        st.markdown('<div class="eyebrow">Etapa 3</div>', unsafe_allow_html=True)
        st.subheader("Resultado pronto para download")
        coverage = (result.calculated / result.total * 100) if result.total else 0
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de rotas", result.total)
        col2.metric("Calculadas", result.calculated)
        col3.metric("Não calculadas", result.failed)
        col4.metric("Taxa de sucesso", f"{coverage:.1f}%")
        st.markdown(
            f'<div class="result-callout"><strong>{result.calculated} rota(s) pronta(s).</strong> '
            'O arquivo inclui coordenadas, distância GPS, hodômetro, percentual de diferença e links clicáveis.</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            st.session_state.get("result_download_label", "Baixar planilha processada"),
            data=result.workbook,
            file_name=st.session_state["result_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
        )

    if source == "Enviar planilha Excel":
        st.markdown(
        """
        <div class="requirements">
          <strong>Colunas obrigatórias na primeira linha</strong><br><br>
          <code>COORDENADA GPS INICIAL</code> e <code>COORDENADA GPS FINAL</code>
        </div>
        """,
        unsafe_allow_html=True,
        )

with analysis_tab:
    if "processed_df" not in st.session_state:
        st.info("Processe uma planilha na aba Calcular Rotas. A análise será exibida automaticamente aqui.")
    else:
        st.header("Análise das Rotas")
        render_dashboard(st.session_state["processed_df"], st.session_state["original_name"], light_mode)

with map_tab:
    if "processed_df" not in st.session_state:
        st.info("Processe uma planilha na aba Calcular Rotas para visualizar os trajetos no mapa 3D.")
    else:
        render_route_map(st.session_state["processed_df"], light_mode)
