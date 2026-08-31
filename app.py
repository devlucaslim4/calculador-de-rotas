"""Interface de cálculo de rotas com apresentação aprovada em prévia."""
from __future__ import annotations

import hashlib
import html
import logging

import streamlit as st

from dashboard import dataframe_from_excel, render_dashboard
from route_processor import SpreadsheetError, output_filename, process_workbook
from ui_theme import apply_theme, render_analysis_empty, render_guide

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
st.set_page_config(page_title="Calculador de Rotas", layout="wide")

light_mode = bool(st.session_state.get("light_mode", False))
apply_theme(light_mode)

brand, theme = st.columns([3, 1])
with brand:
    st.markdown('<div class="rp-brand"><span class="rp-symbol" aria-hidden="true">↗</span>Calculador de Rotas</div>', unsafe_allow_html=True)
with theme:
    st.toggle("Tema claro", key="light_mode", help="Alternar entre os temas claro e escuro")

st.markdown('<div class="rp-heading"><h1>Suas rotas, organizadas.</h1><p>Da planilha às distâncias calculadas, em um só lugar.</p></div>', unsafe_allow_html=True)

route_tab, analysis_tab = st.tabs(["Calcular rotas", "Análise de dados"])

with route_tab:
    # Os componentes nativos mantêm upload, teclado e execução no servidor.
    upload_column, guide_column = st.columns([2.4, 1], gap="large")
    with upload_column:
        with st.container(key="upload_panel"):
            st.markdown('<div class="rp-section"><strong>Importar planilha</strong><span>.xlsx</span></div><div class="rp-upload-heading"><div class="rp-symbol" aria-hidden="true">↑</div><strong>Sua próxima rota começa aqui</strong><p>Selecione a planilha com as coordenadas.</p></div>', unsafe_allow_html=True)
            uploaded_file = st.file_uploader(
                "Selecionar planilha Excel (.xlsx), até 25 MB",
                type=["xlsx"], max_upload_size=25, label_visibility="collapsed",
            )
            st.markdown('<p class="rp-note">O resultado mantém as colunas da sua planilha.</p>', unsafe_allow_html=True)
    with guide_column:
        render_guide()

    with st.expander("Quais colunas minha planilha precisa ter?"):
        st.markdown('''<div class="rp-schema">
          <div><code>COORDENADA GPS INICIAL</code>Origem · exemplo: -23.5505, -46.6333</div>
          <div><code>COORDENADA GPS FINAL</code>Destino · exemplo: -22.9068, -43.1729</div>
        </div>''', unsafe_allow_html=True)
        st.caption("Use os cabeçalhos na primeira linha da aba ativa. Informe latitude e longitude separadas por vírgula.")

    # Identidade pelo conteúdo evita exibir resultados de outro arquivo com mesmo nome/tamanho.
    original_bytes = uploaded_file.getvalue() if uploaded_file is not None else None
    upload_token = (uploaded_file.name, hashlib.sha256(original_bytes).hexdigest()) if uploaded_file is not None else None
    if st.session_state.get("upload_token") != upload_token:
        for key in ("result", "result_name", "original_df", "processed_df", "original_name"):
            st.session_state.pop(key, None)
        st.session_state["upload_token"] = upload_token

    if uploaded_file is not None:
        st.markdown(f'<div class="file-name">{html.escape(uploaded_file.name)}</div>', unsafe_allow_html=True)
        if st.button("Calcular rotas", type="primary", use_container_width=True):
            if not uploaded_file.name.lower().endswith(".xlsx"):
                st.error("Envie um arquivo no formato .xlsx.")
            else:
                progress = st.progress(0, text="Validando a planilha…")

                def update_progress(done: int, total: int) -> None:
                    progress.progress(done / max(total, 1), text=f"Calculando rotas: {done} de {total}")

                try:
                    original_df = dataframe_from_excel(original_bytes)
                    with st.spinner("Consultando as distâncias rodoviárias…"):
                        summary = process_workbook(original_bytes, update_progress)
                    processed_df = dataframe_from_excel(summary.workbook)
                    progress.progress(1.0, text="Processamento concluído")
                    st.session_state.update(
                        result=summary,
                        result_name=output_filename(uploaded_file.name),
                        original_df=original_df,
                        processed_df=processed_df,
                        original_name=uploaded_file.name,
                    )
                    st.success("Planilha processada. Baixe o resultado ou abra a aba Análise de dados.")
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
            "Baixar planilha processada", result.workbook,
            st.session_state["result_name"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", use_container_width=True,
        )

with analysis_tab:
    if "processed_df" not in st.session_state:
        render_analysis_empty()
    else:
        st.header("Análise das rotas")
        render_dashboard(st.session_state["processed_df"], st.session_state["original_name"], light_mode)

st.markdown('<div class="rp-footer"><span>Calculador de Rotas</span><span>As coordenadas são consultadas no serviço OSRM.</span></div>', unsafe_allow_html=True)
