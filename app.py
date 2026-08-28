"""Interface web do Calculador de Rotas."""

from __future__ import annotations

import html
import logging

import streamlit as st

from dashboard import dataframe_from_excel, render_dashboard
from route_processor import SpreadsheetError, output_filename, process_workbook
from ui_helpers import build_template_workbook, validate_upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
st.set_page_config(page_title="Calculador de Rotas", page_icon="🧭", layout="wide")

light_mode = bool(st.session_state.get("light_mode", False))


def inject_styles(is_light: bool) -> None:
    """Aplica uma camada visual sem substituir os componentes acessíveis nativos."""
    colors = {
        "bg": "#F4F7FB" if is_light else "#080A0E",
        "surface": "#FFFFFF" if is_light else "#111722",
        "surface_2": "#F8FAFC" if is_light else "#151C28",
        "text": "#172033" if is_light else "#F1F5F9",
        "muted": "#526175" if is_light else "#AEB8C8",
        "line": "#D7E0EC" if is_light else "#293142",
        "accent": "#2563EB" if is_light else "#60A5FA",
        "soft": "#EFF6FF" if is_light else "#10213C",
    }
    st.markdown(
        f"""
        <style>
        :root{{--app-bg:{colors['bg']};--surface:{colors['surface']};--surface-2:{colors['surface_2']};--text:{colors['text']};--muted:{colors['muted']};--line:{colors['line']};--accent:{colors['accent']};--soft:{colors['soft']}}}
        .stApp{{background:var(--app-bg);color:var(--text)}}
        [data-testid="stHeader"]{{background:color-mix(in srgb,var(--app-bg) 90%,transparent);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}}
        .block-container{{max-width:1240px;padding:2.4rem 2rem 4rem}}
        h1,h2,h3{{color:var(--text);letter-spacing:-.025em}}
        .app-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:2rem;margin-bottom:1.2rem}}
        .app-header h1{{font-size:clamp(2rem,4vw,2.7rem);margin:0 0 .4rem}}
        .app-header p{{color:var(--muted);font-size:1rem;line-height:1.6;max-width:720px;margin:0}}
        .privacy-note{{color:var(--muted);font-size:.78rem;border:1px solid var(--line);border-radius:999px;padding:.45rem .75rem;white-space:nowrap;background:var(--surface)}}
        [data-testid="stTabs"] [data-baseweb="tab-list"]{{gap:.35rem;border-bottom:1px solid var(--line);margin-bottom:1.1rem}}
        [data-testid="stTabs"] button{{min-height:3.25rem;padding:0 1.2rem;border-radius:10px 10px 0 0;color:var(--muted);font-weight:650}}
        [data-testid="stTabs"] button[aria-selected="true"]{{color:var(--accent);background:var(--soft)}}
        [data-testid="stTabs"] [data-baseweb="tab-highlight"]{{background:var(--accent);height:3px}}
        [data-testid="stFileUploader"]{{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1rem;box-shadow:0 10px 28px rgba(0,0,0,.08)}}
        [data-testid="stFileUploaderDropzone"]{{min-height:150px;background:var(--surface-2);border:1.5px dashed color-mix(in srgb,var(--accent) 55%,var(--line));border-radius:12px}}
        [data-testid="stFileUploaderDropzoneInstructions"] span{{font-size:0}}
        [data-testid="stFileUploaderDropzoneInstructions"] span:after{{content:"Arraste o arquivo aqui ou clique para selecionar";font-size:.95rem;color:var(--text);font-weight:650}}
        [data-testid="stFileUploaderDropzoneInstructions"] small{{font-size:0}}
        [data-testid="stFileUploaderDropzoneInstructions"] small:after{{content:"Limite de 25 MB • formato XLSX";font-size:.76rem;color:var(--muted)}}
        [data-testid="stFileUploaderDropzone"] button{{font-size:0;border-radius:9px;background:var(--accent);border-color:var(--accent);color:white}}
        [data-testid="stFileUploaderDropzone"] button:after{{content:"Selecionar arquivo";font-size:.85rem;color:white}}
        .empty-card{{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:clamp(1.2rem,3vw,2rem);margin-top:1rem}}
        .empty-card h3{{margin:.1rem 0 .35rem;font-size:1.25rem}}.empty-card>p{{color:var(--muted);margin:0 0 1.4rem}}
        .steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem}}
        .step{{background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:1rem}}
        .step-number{{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:var(--soft);color:var(--accent);font-weight:750;margin-bottom:.75rem}}
        .step strong{{display:block;color:var(--text);font-size:.9rem;margin-bottom:.25rem}}.step span{{display:block;color:var(--muted);font-size:.78rem;line-height:1.45}}
        .schema{{display:flex;gap:.55rem;flex-wrap:wrap;margin:.8rem 0 0}}.schema code{{background:var(--soft);color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 25%,var(--line));padding:.45rem .65rem;border-radius:7px;font-size:.78rem;overflow-wrap:anywhere}}
        .file-summary{{display:flex;justify-content:space-between;align-items:center;gap:1rem;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.9rem 1rem;margin:.8rem 0}}
        .file-summary strong{{display:block;color:var(--text);font-size:.9rem}}.file-summary span{{color:var(--muted);font-size:.78rem}}
        [data-testid="stAlert"],div[data-testid="stMetric"]{{border-radius:12px;border-width:1px}}
        div[data-testid="stMetric"]{{background:var(--surface);border:1px solid var(--line);padding:1rem}}
        [data-testid="stDataFrame"]{{border:1px solid var(--line);border-radius:12px;overflow:hidden}}
        .stButton>button,.stDownloadButton>button{{min-height:2.9rem;border-radius:10px;font-weight:650}}
        .section-heading{{margin:1.4rem 0 .75rem}}.section-heading strong{{display:block;color:var(--text);font-size:1.05rem}}.section-heading span{{color:var(--muted);font-size:.84rem}}
        @media(max-width:720px){{.block-container{{padding:1.2rem .9rem 3rem}}.app-header{{display:block}}.privacy-note{{display:inline-block;margin-top:.8rem}}.steps{{grid-template-columns:1fr}}[data-testid="stTabs"] button{{padding:0 .7rem;font-size:.85rem}}.file-summary{{align-items:flex-start;flex-direction:column}}}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        '<div class="app-header"><div><h1>Calculador de Rotas</h1><p>Calcule distâncias rodoviárias a partir de uma planilha e explore os resultados em um painel interativo.</p></div><span class="privacy-note">🔒 Processamento em memória</span></div>',
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-card">
          <h3>Comece com sua planilha de rotas</h3>
          <p>Use o modelo abaixo ou prepare seu próprio arquivo seguindo três passos simples.</p>
          <div class="steps">
            <div class="step"><div class="step-number">1</div><strong>Prepare o arquivo</strong><span>Use uma planilha Excel no formato .xlsx.</span></div>
            <div class="step"><div class="step-number">2</div><strong>Informe as coordenadas</strong><span>Preencha origem e destino no formato latitude, longitude.</span></div>
            <div class="step"><div class="step-number">3</div><strong>Envie e processe</strong><span>Confira a prévia e inicie o cálculo das rotas.</span></div>
          </div>
          <div class="schema"><code>COORDENADA GPS INICIAL</code><code>COORDENADA GPS FINAL</code></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, _ = st.columns([1, 2])
    left.download_button(
        "⬇️ Baixar planilha modelo",
        build_template_workbook(),
        "modelo_calculador_de_rotas.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.caption("Você pode manter outras colunas na planilha; elas serão preservadas no resultado.")


def clear_previous_result(upload_token: tuple[str, int]) -> None:
    if st.session_state.get("upload_token") == upload_token:
        return
    for key in ("result", "result_name", "original_df", "processed_df", "original_name"):
        st.session_state.pop(key, None)
    st.session_state["upload_token"] = upload_token


inject_styles(light_mode)
render_header()
st.toggle("Tema claro", key="light_mode", help="Alternar entre tema escuro e claro")

route_tab, analysis_tab = st.tabs(["🧭 Calcular rotas", "📊 Análise de dados"])

with route_tab:
    st.markdown('<div class="section-heading"><strong>Envie sua planilha</strong><span>Você poderá revisar os dados antes de iniciar o processamento.</span></div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Planilha Excel", type=["xlsx"], max_upload_size=25, label_visibility="collapsed")

    if uploaded_file is None:
        render_empty_state()
    else:
        clear_previous_result((uploaded_file.name, uploaded_file.size))
        preview = validate_upload(uploaded_file.getvalue())
        safe_name = html.escape(uploaded_file.name)
        st.markdown(f'<div class="file-summary"><div><strong>📄 {safe_name}</strong><span>Arquivo recebido</span></div><span>{uploaded_file.size / 1024:.1f} KB</span></div>', unsafe_allow_html=True)

        if not preview.valid:
            st.error(preview.error, icon="⚠️")
            with st.expander("Como preparar minha planilha"):
                st.write("Use a primeira linha para os cabeçalhos e inclua as colunas abaixo:")
                st.code("COORDENADA GPS INICIAL | COORDENADA GPS FINAL", language=None)
                st.write("Exemplo de coordenada: `-23.5505, -46.6333`")
                st.download_button("Baixar planilha modelo", build_template_workbook(), "modelo_calculador_de_rotas.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            dataframe = preview.dataframe
            st.success("Planilha validada. Revise a prévia e, se estiver tudo certo, processe as rotas.", icon="✅")
            metric_1, metric_2, metric_3 = st.columns(3)
            metric_1.metric("Rotas carregadas", len(dataframe))
            metric_2.metric("Colunas", len(dataframe.columns))
            metric_3.metric("Prévia", f"{min(8, len(dataframe))} linhas")
            st.markdown('<div class="section-heading"><strong>Prévia dos dados</strong><span>Primeiras linhas da aba ativa.</span></div>', unsafe_allow_html=True)
            st.dataframe(dataframe.head(8), use_container_width=True, hide_index=True, height=min(330, 42 + 35 * min(8, len(dataframe))))

            with st.expander("Como preparar minha planilha"):
                st.write("As coordenadas devem usar o formato `latitude, longitude`. As demais colunas e abas serão preservadas sempre que possível.")

            if st.button("Calcular rotas", type="primary", use_container_width=True):
                progress = st.progress(0, text="Validando a planilha…")

                def update_progress(done: int, total: int) -> None:
                    fraction = .08 + (.84 * done / max(total, 1))
                    progress.progress(fraction, text=f"Calculando rotas: {done} de {total}")

                try:
                    original_bytes = uploaded_file.getvalue()
                    progress.progress(.08, text="Planilha validada. Consultando as rotas…")
                    summary = process_workbook(original_bytes, update_progress)
                    progress.progress(.96, text="Preparando o arquivo final…")
                    processed_df = dataframe_from_excel(summary.workbook)
                    st.session_state.update(
                        result=summary,
                        result_name=output_filename(uploaded_file.name),
                        original_df=dataframe,
                        processed_df=processed_df,
                        original_name=uploaded_file.name,
                    )
                    progress.progress(1.0, text="Processamento concluído")
                    st.success("Tudo pronto! Baixe a planilha calculada ou abra a aba Análise de dados.", icon="✅")
                except SpreadsheetError as exc:
                    progress.empty()
                    st.error(f"Não foi possível processar a planilha: {exc}", icon="⚠️")
                except Exception:
                    logging.exception("Erro inesperado no processamento")
                    progress.empty()
                    st.error("O processamento não foi concluído. Verifique sua conexão e tente novamente. Se o problema continuar, aguarde alguns minutos.", icon="⚠️")

    if "result" in st.session_state:
        result = st.session_state["result"]
        st.markdown('<div class="section-heading"><strong>Resultado do processamento</strong><span>Resumo das rotas calculadas no arquivo atual.</span></div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", result.total)
        col2.metric("Calculadas", result.calculated)
        col3.metric("Não calculadas", result.failed)
        st.download_button(
            "⬇️ Baixar planilha calculada",
            result.workbook,
            st.session_state["result_name"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

with analysis_tab:
    if "processed_df" not in st.session_state:
        st.markdown(
            """
            <div class="empty-card">
              <h3>📊 Sua análise aparecerá aqui</h3>
              <p>Envie e processe uma planilha na aba Calcular rotas. Os indicadores, gráficos e filtros serão preparados automaticamente, sem refazer as consultas.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.header("Análise das rotas")
        st.caption(f"Arquivo: {st.session_state['original_name']}")
        render_dashboard(st.session_state["processed_df"], st.session_state["original_name"], light_mode)
