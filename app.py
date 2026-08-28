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
:root{--orange:#ED6500;--dark:#1F2227;--ink:#17191D;--muted:#73777F;--line:#E8E9EB;--canvas:#FAFAFA}
.stApp{background:var(--canvas);color:var(--ink)} [data-testid="stHeader"]{background:rgba(250,250,250,.94);backdrop-filter:blur(12px)}
[data-testid="stToolbar"],#MainMenu,footer{visibility:hidden}.block-container{max-width:1280px;padding:2rem 2.6rem 4rem}
[data-testid="stSidebar"]{background:#191B1F;border-right:1px solid #25282D}[data-testid="stSidebar"] *{color:#F7F7F8}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.35rem}[data-testid="stSidebar"] label[data-baseweb="radio"]{padding:.75rem .85rem;border-radius:10px;transition:.2s}
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{background:#24272C}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked){background:#2A2D32;border-left:3px solid var(--orange)}
[data-testid="stSidebar"] label[data-baseweb="radio"]>div:first-child{display:none}
.sidebar-brand{display:flex;align-items:center;gap:.7rem;padding:.25rem .25rem 1.25rem;border-bottom:1px solid #303238;margin-bottom:1rem}.sidebar-brand strong{display:block;font-size:.92rem}.sidebar-brand span{color:#9B9FA8!important;font-size:.7rem}
.brand-mark{display:grid;place-items:center;width:38px;height:38px;border-radius:8px;background:var(--orange);font:bold 1.2rem sans-serif}.brand-logo{width:38px;height:38px;border-radius:8px;object-fit:contain;background:#fff}
.sidebar-footer{margin-top:2rem;padding:1rem .3rem;color:#94A3B8!important;font-size:.75rem;line-height:1.5}
.app-header{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding-bottom:1.4rem;margin-bottom:1.5rem;border-bottom:1px solid var(--line)}.eyebrow{color:var(--orange);font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.app-header h1{color:var(--ink);font-size:clamp(1.55rem,3vw,2rem);letter-spacing:-.035em;margin:.2rem 0}.app-header p{color:var(--muted);margin:0;font-size:.92rem}
.overview-panel{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(240px,.6fr);gap:2rem;align-items:center;background:#fff;border:1px solid var(--line);border-radius:12px;padding:2rem;margin-bottom:1.5rem}.overview-panel h2{font-size:1.55rem;margin:0 0 .55rem;color:var(--ink);letter-spacing:-.025em}.overview-panel p{color:var(--muted);line-height:1.6;margin:0}.overview-logo{display:flex;justify-content:center}.overview-logo img{width:112px;height:112px;object-fit:contain}
.steps{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-top:1rem}.step{padding:1.2rem;border-right:1px solid var(--line)}.step:last-child{border-right:0}.step small{display:block;color:var(--orange);font-weight:750;margin-bottom:.35rem}.step strong{font-size:.9rem;color:var(--ink)}.step span{display:block;color:var(--muted);font-size:.78rem;margin-top:.25rem}
.section-title{margin:1.7rem 0 .9rem}.section-title h2{color:var(--ink);font-size:1.18rem;margin:0}.section-title p{color:var(--muted);margin:.3rem 0 0;font-size:.9rem}
[data-testid="stMetric"]{min-height:112px;background:#fff;border:1px solid var(--line);border-radius:10px;padding:1rem;box-shadow:none}[data-testid="stMetricLabel"]{color:var(--muted)}[data-testid="stMetricValue"]{color:var(--ink)}
[data-testid="stFileUploader"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:1rem;box-shadow:none}[data-testid="stFileUploaderDropzone"]{background:#FCFCFC;border:1.5px dashed #D4D6DA;border-radius:9px;min-height:150px}[data-testid="stFileUploaderDropzone"] svg{color:var(--orange);fill:var(--orange)}
.file-card{display:flex;justify-content:space-between;align-items:center;gap:1rem;background:#fff;border:1px solid var(--line);padding:1rem 1.1rem;border-radius:9px;margin:.8rem 0}.file-card strong{color:var(--ink)}.file-card span{color:var(--muted);font-size:.82rem}
.stButton>button,.stDownloadButton>button{min-height:3rem;border-radius:10px;font-weight:700;transition:.2s}.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:var(--orange);border-color:var(--orange);color:#fff;box-shadow:0 7px 18px rgba(244,81,30,.2)}
[data-testid="stAlert"]{border-radius:9px}[data-testid="stProgress"]>div>div>div{background:var(--orange)}[data-testid="stPlotlyChart"],[data-testid="stDataFrame"]{background:#fff;border:1px solid var(--line);border-radius:10px;padding:.4rem;box-shadow:none;overflow:hidden}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--line)}[data-testid="stTabs"] button[aria-selected="true"]{color:var(--orange)}
.info-panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1.25rem;color:#475467;line-height:1.65}.info-panel strong{color:var(--ink)}.info-panel code{color:#D84315;background:#FFF1EB;padding:.15rem .35rem;border-radius:5px}
@media(max-width:760px){.block-container{padding:1rem 1rem 3rem}.app-header{align-items:flex-start}.overview-panel{grid-template-columns:1fr}.overview-logo{display:none}.steps{grid-template-columns:1fr}.step{border-right:0;border-bottom:1px solid var(--line)}.file-card{align-items:flex-start;flex-direction:column}}
</style>
""", unsafe_allow_html=True)


def header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="app-header"><div><div class="eyebrow">Calculadora de rotas</div><h1>{title}</h1><p>{subtitle}</p></div></div>', unsafe_allow_html=True)


def section(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="section-title"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)


def overview() -> None:
    header("Visão geral", "Cálculo e análise de distâncias rodoviárias em planilhas.")
    st.markdown(f'<div class="overview-panel"><div><h2>Calcule suas rotas em poucos passos</h2><p>Importe uma planilha Excel com as coordenadas de origem e destino. O sistema calcula as distâncias e devolve o arquivo pronto para uso.</p></div><div class="overview-logo">{logo()}</div></div><div class="steps"><div class="step"><small>01</small><strong>Envie a planilha</strong><span>Arquivo Excel de até 25 MB</span></div><div class="step"><small>02</small><strong>Processe as rotas</strong><span>Acompanhe o cálculo em tempo real</span></div><div class="step"><small>03</small><strong>Baixe o resultado</strong><span>Planilha e análises prontas</span></div></div>', unsafe_allow_html=True)
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


def help_page() -> None:
    header("Ajuda", "Orientações rápidas para preparar e processar sua planilha.")
    st.markdown('<div class="info-panel"><strong>Como usar</strong><br><br>1. Acesse <b>Calcular Rotas</b> e selecione um arquivo .xlsx.<br>2. Confirme as colunas obrigatórias na primeira linha da aba ativa.<br>3. Clique em <b>Processar rotas</b> e aguarde.<br>4. Baixe o resultado ou abra <b>Análises</b>.<br><br><strong>Coordenadas</strong><br>Use latitude e longitude separadas por vírgula: <code>-23.5505, -46.6333</code>.<br><br><strong>Privacidade</strong><br>A planilha é tratada em memória. As coordenadas são enviadas ao serviço público OSRM.</div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown(f'<div class="sidebar-brand">{logo()}<div><strong>Portal de Rotas</strong><span>Gestão operacional</span></div></div>', unsafe_allow_html=True)
    page = st.radio("Navegação", ["Visão geral", "Calcular rotas", "Análises", "Ajuda"], label_visibility="collapsed")
    st.markdown('<div class="sidebar-footer">Uso interno<br>Arquivos processados em memória</div>', unsafe_allow_html=True)

{"Visão geral": overview, "Calcular rotas": calculator, "Análises": analytics, "Ajuda": help_page}[page]()
