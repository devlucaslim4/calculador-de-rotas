"""Interface web do Calculador de Rotas."""

from __future__ import annotations

import logging

import streamlit as st

from dashboard import dataframe_from_excel, render_dashboard
from route_processor import SpreadsheetError, output_filename, process_workbook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
st.set_page_config(page_title="Calculador de Rotas", layout="wide")

light_mode = bool(st.session_state.get("light_mode", False))

st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at 50% 0%, #172033 0%, #0b0d12 42%, #07080b 100%); }
    .block-container { max-width: 1240px; padding-top: 3rem; padding-bottom: 4rem; }
    [data-testid="stFileUploader"], [data-testid="stAlert"], div[data-testid="stMetric"] {
        background: rgba(18, 22, 31, .82); border: 1px solid #293142; border-radius: 16px;
        padding: 1rem; box-shadow: 0 12px 32px rgba(0,0,0,.18);
    }
    h1 { letter-spacing: -.04em; }
    .subtitle { color: #aeb8c8; font-size: 1.05rem; line-height: 1.65; max-width: 760px; margin-bottom: 1.8rem; }
    .file-name { color: #cbd5e1; background: #111722; border: 1px solid #273247; padding: .7rem 1rem; border-radius: 12px; margin: .5rem 0 1rem; }
    .requirements { margin-top: 2rem; padding: 1.25rem 1.4rem; border: 1px solid #252c3a; border-radius: 16px; background: rgba(14,17,23,.7); color: #aeb8c8; }
    .requirements code { color: #93c5fd; }
    .stButton > button, .stDownloadButton > button { border-radius: 12px; min-height: 3rem; font-weight: 650; }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .5rem; }
    [data-testid="stTabs"] button { border-radius: 10px; padding-left: 1rem; padding-right: 1rem; }
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
        </style>
        """,
        unsafe_allow_html=True,
    )

st.title("Calculador de Rotas")
st.markdown(
    '<div class="subtitle">Envie sua planilha, calcule as distâncias das rotas e consulte os resultados na aba de análise.</div>',
    unsafe_allow_html=True,
)
st.toggle("Usar tema claro", key="light_mode", help="Alterna a aparência entre os temas escuro e claro")

route_tab, analysis_tab = st.tabs(["Calcular Rotas", "Análise de Dados"])

with route_tab:
    uploaded_file = st.file_uploader("Envie uma planilha Excel (.xlsx)", type=["xlsx"], max_upload_size=25)

    if uploaded_file is not None:
        upload_token = (uploaded_file.name, uploaded_file.size)
        if st.session_state.get("upload_token") != upload_token:
            for key in ("result", "result_name", "original_df", "processed_df", "original_name"):
                st.session_state.pop(key, None)
            st.session_state["upload_token"] = upload_token

        st.markdown(f'<div class="file-name">{uploaded_file.name}</div>', unsafe_allow_html=True)

        if st.button("Calcular distâncias", type="primary", use_container_width=True):
            if not uploaded_file.name.lower().endswith(".xlsx"):
                st.error("Envie um arquivo no formato .xlsx.")
            else:
                progress = st.progress(0, text="Validando a planilha…")

                def update_progress(done: int, total: int) -> None:
                    progress.progress(done / total, text=f"Calculando rotas: {done} de {total}")

                try:
                    original_bytes = uploaded_file.getvalue()
                    original_df = dataframe_from_excel(original_bytes)
                    with st.spinner("Consultando as distâncias rodoviárias…"):
                        summary = process_workbook(original_bytes, update_progress)
                    processed_df = dataframe_from_excel(summary.workbook)
                    progress.progress(1.0, text="Processamento concluído")
                    st.session_state["result"] = summary
                    st.session_state["result_name"] = output_filename(uploaded_file.name)
                    st.session_state["original_df"] = original_df
                    st.session_state["processed_df"] = processed_df
                    st.session_state["original_name"] = uploaded_file.name
                    st.success("Planilha processada com sucesso. Consulte os resultados abaixo ou abra a aba Análise de Dados.")
                except SpreadsheetError as exc:
                    progress.empty()
                    st.error(str(exc))
                except Exception:
                    logging.exception("Erro inesperado no processamento")
                    progress.empty()
                    st.error("Não foi possível concluir o processamento. Verifique o arquivo e tente novamente em alguns instantes.")

    if "result" in st.session_state:
        result = st.session_state["result"]
        st.subheader("Resultado")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de rotas", result.total)
        col2.metric("Calculadas", result.calculated)
        col3.metric("Não calculadas", result.failed)
        st.download_button(
            "Baixar planilha processada",
            data=result.workbook,
            file_name=st.session_state["result_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

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
