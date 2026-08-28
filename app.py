"""Portal corporativo do Calculador de Rotas."""
from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path

import streamlit as st

from dashboard import dataframe_from_excel, render_dashboard
from route_processor import SpreadsheetError, output_filename, process_workbook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "logo.png"

st.set_page_config(page_title="Portal de Rotas", page_icon="🚚", layout="wide", initial_sidebar_state="expanded")


def logo() -> str:
    if LOGO_PATH.exists():
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        return f'<img class="brand-logo" src="data:image/png;base64,{data}" alt="Logo da empresa">'
    return '<div class="brand-mark">R</div>'


st.markdown("""
<style>
:root{--orange:#F4511E;--dark:#303842;--ink:#111827;--muted:#667085;--line:#E5E7EB;--canvas:#F5F6F8}
.stApp{background:var(--canvas);color:var(--ink)} [data-testid="stHeader"]{background:rgba(245,246,248,.9);backdrop-filter:blur(12px)}
[data-testid="stToolbar"],#MainMenu,footer{visibility:hidden}.block-container{max-width:1440px;padding:1.7rem 2.25rem 4rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#303842,#232930);border:0}[data-testid="stSidebar"] *{color:#F9FAFB}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.35rem}[data-testid="stSidebar"] label[data-baseweb="radio"]{padding:.75rem .85rem;border-radius:10px;transition:.2s}
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{background:rgba(255,255,255,.08);transform:translateX(2px)}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked){background:var(--orange);box-shadow:0 8px 20px rgba(244,81,30,.25)}
.sidebar-brand{display:flex;align-items:center;gap:.75rem;padding:.35rem .25rem 1.4rem;border-bottom:1px solid rgba(255,255,255,.12);margin-bottom:1rem}.sidebar-brand strong{display:block}.sidebar-brand span{color:#CBD5E1!important;font-size:.75rem}
.brand-mark{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:linear-gradient(145deg,#FF7043,var(--orange));font:bold 1.3rem sans-serif;box-shadow:0 8px 20px rgba(244,81,30,.3)}.brand-logo{max-height:42px;max-width:120px;object-fit:contain}
.sidebar-footer{margin-top:2rem;padding:1rem .3rem;color:#94A3B8!important;font-size:.75rem;line-height:1.5}
.app-header{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:1.6rem}.eyebrow{color:var(--orange);font-size:.76rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}.app-header h1{color:var(--ink);font-size:clamp(1.65rem,3vw,2.35rem);letter-spacing:-.045em;margin:.25rem 0}.app-header p{color:var(--muted);margin:0}
.status-pill{display:flex;align-items:center;gap:.5rem;background:#fff;border:1px solid var(--line);border-radius:999px;padding:.55rem .85rem;color:#344054;font-size:.82rem;font-weight:650;white-space:nowrap}.status-dot{width:8px;height:8px;border-radius:50%;background:#16A34A;box-shadow:0 0 0 4px #DCFCE7}
.hero{position:relative;overflow:hidden;border-radius:20px;padding:clamp(1.4rem,3vw,2.3rem);color:#fff;background:linear-gradient(120deg,#303842,#404A56 65%,#F4511E 160%);box-shadow:0 18px 44px rgba(48,56,66,.16);margin-bottom:1.4rem}.hero:after{content:"";position:absolute;width:260px;height:260px;right:-80px;top:-120px;border:45px solid rgba(244,81,30,.45);border-radius:50%}.hero h2{color:#fff;font-size:clamp(1.45rem,3vw,2.15rem);margin:0 0 .55rem}.hero p{color:#E2E8F0;max-width:740px;margin:0;line-height:1.65}
.section-title{margin:1.7rem 0 .9rem}.section-title h2{color:var(--ink);font-size:1.18rem;margin:0}.section-title p{color:var(--muted);margin:.3rem 0 0;font-size:.9rem}
[data-testid="stMetric"]{min-height:128px;background:#fff;border:1px solid var(--line);border-top:3px solid var(--orange);border-radius:16px;padding:1.1rem;box-shadow:0 5px 18px rgba(16,24,40,.045);transition:.2s}[data-testid="stMetric"]:hover{transform:translateY(-2px)}[data-testid="stMetricLabel"]{color:var(--muted)}[data-testid="stMetricValue"]{color:var(--ink)}
[data-testid="stFileUploader"]{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1.1rem;box-shadow:0 8px 26px rgba(16,24,40,.05)}[data-testid="stFileUploaderDropzone"]{background:#FFF8F5;border:1.5px dashed #FFAB91;border-radius:14px;min-height:155px}[data-testid="stFileUploaderDropzone"] svg{color:var(--orange);fill:var(--orange)}
.file-card{display:flex;justify-content:space-between;align-items:center;gap:1rem;background:#fff;border:1px solid var(--line);border-left:4px solid var(--orange);padding:1rem 1.1rem;border-radius:13px;margin:.8rem 0}.file-card strong{color:var(--ink)}.file-card span{color:var(--muted);font-size:.82rem}
.stButton>button,.stDownloadButton>button{min-height:3rem;border-radius:10px;font-weight:700;transition:.2s}.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:var(--orange);border-color:var(--orange);color:#fff;box-shadow:0 7px 18px rgba(244,81,30,.2)}
[data-testid="stAlert"]{border-radius:13px}[data-testid="stProgress"]>div>div>div{background:var(--orange)}[data-testid="stPlotlyChart"],[data-testid="stDataFrame"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:.4rem;box-shadow:0 4px 16px rgba(16,24,40,.04);overflow:hidden}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--line)}[data-testid="stTabs"] button[aria-selected="true"]{color:var(--orange)}
.info-panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1.25rem;color:#475467;line-height:1.65}.info-panel strong{color:var(--ink)}.info-panel code{color:#D84315;background:#FFF1EB;padding:.15rem .35rem;border-radius:5px}
@media(max-width:760px){.block-container{padding:1rem 1rem 3rem}.app-header{align-items:flex-start}.status-pill{display:none}.hero{border-radius:16px}.file-card{align-items:flex-start;flex-direction:column}}
</style>
""", unsafe_allow_html=True)


def header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="app-header"><div><div class="eyebrow">Operações • Logística</div><h1>{title}</h1><p>{subtitle}</p></div><div class="status-pill"><span class="status-dot"></span>Sistema online</div></div>', unsafe_allow_html=True)


def section(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="section-title"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)


def overview() -> None:
    header("Visão Geral", "Acompanhe o processamento e os principais indicadores da sessão.")
    st.markdown('<div class="hero"><h2>Rotas mais simples. Decisões mais rápidas.</h2><p>Envie sua planilha, calcule distâncias rodoviárias e transforme o resultado em uma visão operacional clara — tudo em um único ambiente.</p></div>', unsafe_allow_html=True)
    if "result" not in st.session_state:
        section("Comece um novo processamento", "Os indicadores aparecerão após uma planilha ser calculada.")
        st.info("Acesse **Calcular Rotas** no menu lateral para enviar seu primeiro arquivo nesta sessão.")
        return
    result = st.session_state.result
    rate = result.calculated / result.total * 100 if result.total else 0
    section("Último processamento", "Dados reais do arquivo calculado nesta sessão.")
    for col, label, value in zip(st.columns(4), ["Rotas processadas", "Rotas calculadas", "Falhas", "Taxa de sucesso"], [result.total, result.calculated, result.failed, f"{rate:.1f}%"]): col.metric(label, value)
    st.markdown(f'<div class="file-card"><div><strong>{st.session_state.original_name}</strong><br><span>Processado em {st.session_state.processed_at}</span></div><span>Resultado disponível</span></div>', unsafe_allow_html=True)


def calculator() -> None:
    header("Calcular Rotas", "Faça upload da planilha e acompanhe cada etapa do processamento.")
    section("Importar planilha", "Arquivo Excel (.xlsx), com tamanho máximo de 25 MB.")
    uploaded = st.file_uploader("Arraste a planilha para esta área ou clique para selecionar", type=["xlsx"], max_upload_size=25)
    if uploaded:
        token = (uploaded.name, uploaded.size)
        if st.session_state.get("upload_token") != token:
            for key in ("result", "result_name", "original_df", "processed_df", "original_name", "processed_at"): st.session_state.pop(key, None)
            st.session_state.upload_token = token
        size = f"{uploaded.size / 1024:.1f} KB" if uploaded.size < 1048576 else f"{uploaded.size / 1048576:.1f} MB"
        st.markdown(f'<div class="file-card"><div><strong>📄 {uploaded.name}</strong><br><span>Pronta para validação</span></div><span>{size}</span></div>', unsafe_allow_html=True)
        if st.button("Processar rotas", type="primary", use_container_width=True):
            progress = st.progress(0, text="Arquivo recebido")
            try:
                raw = uploaded.getvalue(); progress.progress(.08, text="Validando estrutura e colunas…")
                original = dataframe_from_excel(raw)
                def update(done: int, total: int) -> None: progress.progress(.12 + .78 * done / max(total, 1), text=f"Calculando rotas • {done} de {total}")
                result = process_workbook(raw, update); progress.progress(.94, text="Gerando arquivo de resultado…")
                st.session_state.update(result=result, result_name=output_filename(uploaded.name), original_df=original, processed_df=dataframe_from_excel(result.workbook), original_name=uploaded.name, processed_at=datetime.now().strftime("%d/%m/%Y às %H:%M"))
                progress.progress(1.0, text="Processamento concluído"); st.success("Processamento concluído. O arquivo e as análises já estão disponíveis.")
            except SpreadsheetError as exc: progress.empty(); st.error(f"Não foi possível validar a planilha: {exc}")
            except Exception: logging.exception("Erro inesperado"); progress.empty(); st.error("Não foi possível concluir o processamento. Revise o arquivo e tente novamente.")
    if "result" in st.session_state:
        result = st.session_state.result; section("Resultado", "Resumo real do último arquivo processado.")
        for col, label, value in zip(st.columns(3), ["Total de rotas", "Calculadas", "Com falha"], [result.total, result.calculated, result.failed]): col.metric(label, value)
        st.download_button("Baixar planilha processada", result.workbook, st.session_state.result_name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
    st.markdown('<div class="info-panel"><strong>Estrutura necessária</strong><br>A primeira linha deve conter <code>COORDENADA GPS INICIAL</code> e <code>COORDENADA GPS FINAL</code>. As demais colunas, abas e formatações são preservadas sempre que possível.</div>', unsafe_allow_html=True)


def analytics() -> None:
    header("Análises", "Explore indicadores, gráficos, filtros e auditoria da planilha processada.")
    if "processed_df" not in st.session_state: st.info("Processe uma planilha em **Calcular Rotas** para liberar esta área.")
    else: render_dashboard(st.session_state.processed_df, st.session_state.original_name, light_mode=True)


def history() -> None:
    header("Histórico", "Consulte o processamento mantido durante esta sessão."); st.caption("Por privacidade, os arquivos não são armazenados permanentemente.")
    if "result" not in st.session_state: st.info("Ainda não há processamentos nesta sessão."); return
    result = st.session_state.result
    st.markdown(f'<div class="file-card"><div><strong>{st.session_state.original_name}</strong><br><span>{st.session_state.processed_at} • {result.total} rotas</span></div><span>{result.calculated} calculadas</span></div>', unsafe_allow_html=True)
    st.download_button("Baixar resultado novamente", result.workbook, st.session_state.result_name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def help_page() -> None:
    header("Ajuda", "Orientações rápidas para preparar e processar sua planilha.")
    st.markdown('<div class="info-panel"><strong>Como usar</strong><br><br>1. Acesse <b>Calcular Rotas</b> e selecione um arquivo .xlsx.<br>2. Confirme as colunas obrigatórias na primeira linha da aba ativa.<br>3. Clique em <b>Processar rotas</b> e aguarde.<br>4. Baixe o resultado ou abra <b>Análises</b>.<br><br><strong>Coordenadas</strong><br>Use latitude e longitude separadas por vírgula: <code>-23.5505, -46.6333</code>.<br><br><strong>Privacidade</strong><br>A planilha é tratada em memória. As coordenadas são enviadas ao serviço público OSRM.</div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown(f'<div class="sidebar-brand">{logo()}<div><strong>Portal de Rotas</strong><span>Gestão operacional</span></div></div>', unsafe_allow_html=True)
    page = st.radio("Navegação", ["Visão Geral", "Calcular Rotas", "Análises", "Histórico", "Ajuda"], label_visibility="collapsed")
    st.markdown('<div class="sidebar-footer">Ambiente corporativo<br>Processamento seguro em memória</div>', unsafe_allow_html=True)

{"Visão Geral": overview, "Calcular Rotas": calculator, "Análises": analytics, "Histórico": history, "Ajuda": help_page}[page]()
