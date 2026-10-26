"""Identidade visual e componentes de apresentação do Calculador de Rotas.

Este módulo não conhece regras de negócio nem dados de rota. Ele concentra os
tokens visuais e pequenos componentes de interface usados pelo Streamlit.
"""

from __future__ import annotations

import html

import streamlit as st


COLORS = {
    "background": "#101C2B",
    "surface": "#1D2D40",
    "surface_soft": "#172639",
    "surface_deep": "#0D1825",
    "border": "#2E4359",
    "primary": "#56CFAD",
    "primary_strong": "#36B895",
    "text": "#F4F7FA",
    "muted": "#A7B7C8",
    "subtle": "#72859A",
}


def apply_theme() -> None:
    """Aplica o design system sem interferir nos componentes funcionais."""

    st.markdown(
        """
        <style>
        :root {
            --route-bg: #101C2B;
            --route-surface: #1D2D40;
            --route-surface-soft: #172639;
            --route-surface-deep: #0D1825;
            --route-border: #2E4359;
            --route-border-soft: rgba(167, 183, 200, .14);
            --route-primary: #56CFAD;
            --route-primary-strong: #36B895;
            --route-primary-soft: rgba(86, 207, 173, .12);
            --route-text: #F4F7FA;
            --route-muted: #A7B7C8;
            --route-subtle: #72859A;
            --route-danger: #F08C8C;
            --route-warning: #E8BE69;
            --route-radius-sm: 10px;
            --route-radius-md: 16px;
            --route-radius-lg: 22px;
            --route-shadow: 0 18px 44px rgba(3, 10, 18, .22);
        }

        html { scroll-behavior: smooth; }
        .stApp {
            color: var(--route-text);
            background:
                radial-gradient(circle at 88% -12%, rgba(86, 207, 173, .10), transparent 32rem),
                linear-gradient(180deg, #101C2B 0%, #0D1825 100%);
        }
        [data-testid="stHeader"] {
            background: rgba(16, 28, 43, .82);
            border-bottom: 1px solid rgba(167, 183, 200, .08);
            backdrop-filter: blur(16px);
        }
        [data-testid="stToolbar"] { right: 1rem; }
        .block-container {
            width: min(100%, 1380px);
            padding-top: 1.35rem;
            padding-bottom: 4.5rem;
        }
        [data-testid="stSidebar"] {
            background: #0D1825;
            border-right: 1px solid var(--route-border-soft);
        }
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.25rem; }
        [data-testid="stSidebar"] hr { border-color: var(--route-border-soft); }

        h1, h2, h3, p, label { color: var(--route-text); }
        h1, h2, h3 { letter-spacing: -.025em; }
        h2 { font-size: clamp(1.35rem, 2vw, 1.75rem) !important; }
        h3 { font-size: 1.1rem !important; }
        [data-testid="stCaptionContainer"] p, .stCaption { color: var(--route-muted) !important; }
        a { color: var(--route-primary); }

        .app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.5rem;
            padding: 1.35rem 1.45rem;
            margin-bottom: 1.35rem;
            border: 1px solid var(--route-border-soft);
            border-radius: var(--route-radius-lg);
            background: linear-gradient(125deg, rgba(29, 45, 64, .98), rgba(23, 38, 57, .96));
            box-shadow: var(--route-shadow);
            overflow: hidden;
            position: relative;
        }
        .app-header::after {
            content: "";
            position: absolute;
            width: 18rem;
            height: 18rem;
            right: -8rem;
            top: -11rem;
            border-radius: 50%;
            background: rgba(86, 207, 173, .07);
            pointer-events: none;
        }
        .brand-lockup { display: flex; align-items: center; gap: 1rem; min-width: 0; z-index: 1; }
        .brand-mark {
            width: 3.15rem;
            height: 3.15rem;
            flex: 0 0 3.15rem;
            display: grid;
            place-items: center;
            border-radius: 15px;
            color: #0D1825;
            background: var(--route-primary);
            box-shadow: 0 10px 24px rgba(86, 207, 173, .18);
        }
        .brand-mark svg { width: 1.75rem; height: 1.75rem; }
        .brand-kicker {
            margin-bottom: .18rem;
            color: var(--route-primary);
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .13em;
            text-transform: uppercase;
        }
        .app-header h1 {
            margin: 0;
            color: var(--route-text);
            font-size: clamp(1.7rem, 3vw, 2.25rem);
            line-height: 1.08;
        }
        .brand-description {
            margin: .4rem 0 0;
            color: var(--route-muted);
            font-size: .95rem;
            line-height: 1.45;
        }
        .connection-status {
            display: inline-flex;
            align-items: center;
            gap: .55rem;
            flex: 0 0 auto;
            z-index: 1;
            padding: .62rem .8rem;
            border: 1px solid rgba(86, 207, 173, .22);
            border-radius: 999px;
            color: #CFF8EC;
            background: rgba(86, 207, 173, .08);
            font-size: .78rem;
            font-weight: 650;
        }
        .connection-status.pending {
            color: #F3D99E;
            border-color: rgba(232, 190, 105, .24);
            background: rgba(232, 190, 105, .08);
        }
        .status-dot {
            width: .48rem;
            height: .48rem;
            border-radius: 50%;
            background: currentColor;
            box-shadow: 0 0 0 4px rgba(86, 207, 173, .09);
        }

        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: .7rem;
            padding: .25rem 0 1rem;
        }
        .sidebar-mark {
            width: 2.15rem;
            height: 2.15rem;
            display: grid;
            place-items: center;
            border-radius: 10px;
            color: #0D1825;
            background: var(--route-primary);
        }
        .sidebar-mark svg { width: 1.3rem; height: 1.3rem; }
        .sidebar-brand strong { display: block; color: var(--route-text); font-size: .98rem; }
        .sidebar-brand span { display: block; color: var(--route-subtle); font-size: .76rem; }
        .sidebar-label {
            margin: .2rem 0 .55rem;
            color: var(--route-subtle);
            font-size: .7rem;
            font-weight: 750;
            letter-spacing: .12em;
            text-transform: uppercase;
        }
        .flow-step {
            display: flex;
            align-items: center;
            gap: .7rem;
            padding: .55rem .05rem;
            color: var(--route-subtle);
            font-size: .85rem;
        }
        .flow-dot {
            width: 1.6rem;
            height: 1.6rem;
            flex: 0 0 1.6rem;
            display: grid;
            place-items: center;
            border: 1px solid var(--route-border);
            border-radius: 50%;
            font-size: .7rem;
            font-weight: 800;
        }
        .flow-step.done { color: #D9E6EF; }
        .flow-step.done .flow-dot {
            color: #0D1825;
            border-color: var(--route-primary);
            background: var(--route-primary);
        }

        .section-heading {
            display: flex;
            gap: .9rem;
            align-items: flex-start;
            margin-bottom: .9rem;
        }
        .section-number {
            min-width: 2.15rem;
            padding-top: .12rem;
            color: var(--route-primary);
            font-size: .74rem;
            font-weight: 800;
            letter-spacing: .1em;
        }
        .section-heading h2 { margin: 0; color: var(--route-text); }
        .section-heading p {
            max-width: 760px;
            margin: .35rem 0 0;
            color: var(--route-muted);
            font-size: .92rem;
            line-height: 1.5;
        }
        .empty-state {
            padding: 2rem 1.4rem;
            text-align: center;
            border: 1px dashed var(--route-border);
            border-radius: var(--route-radius-md);
            background: rgba(23, 38, 57, .5);
        }
        .empty-state strong { display: block; color: var(--route-text); font-size: 1rem; }
        .empty-state span { display: block; margin-top: .35rem; color: var(--route-muted); font-size: .88rem; }
        .file-name {
            margin: .7rem 0 1rem;
            padding: .75rem .9rem;
            color: #DDE9F2;
            border: 1px solid var(--route-border-soft);
            border-radius: var(--route-radius-sm);
            background: var(--route-surface-deep);
            font-size: .86rem;
        }
        .requirements {
            margin-top: 1rem;
            padding: 1rem 1.1rem;
            color: var(--route-muted);
            border: 1px solid var(--route-border-soft);
            border-radius: var(--route-radius-md);
            background: rgba(23, 38, 57, .7);
            font-size: .88rem;
        }
        .requirements strong { color: var(--route-text); }
        .requirements code { color: var(--route-primary); background: rgba(86, 207, 173, .08); }
        .result-callout {
            margin: .65rem 0 1rem;
            padding: 1rem 1.1rem;
            color: #D9F8EF;
            border: 1px solid rgba(86, 207, 173, .25);
            border-radius: var(--route-radius-md);
            background: var(--route-primary-soft);
            line-height: 1.5;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--route-border-soft) !important;
            border-radius: var(--route-radius-lg) !important;
            background: rgba(29, 45, 64, .72);
            box-shadow: 0 12px 34px rgba(3, 10, 18, .12);
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.15rem 1.2rem; }
        div[data-testid="stMetric"] {
            min-height: 7.25rem;
            padding: 1rem 1.05rem;
            border: 1px solid var(--route-border-soft);
            border-radius: var(--route-radius-md);
            background: linear-gradient(145deg, rgba(29, 45, 64, .98), rgba(23, 38, 57, .95));
            box-shadow: 0 12px 30px rgba(3, 10, 18, .14);
            transition: transform .16s ease, border-color .16s ease;
        }
        div[data-testid="stMetric"]:hover { transform: translateY(-2px); border-color: rgba(86, 207, 173, .38); }
        [data-testid="stMetricLabel"] p { color: var(--route-muted) !important; font-size: .78rem; }
        [data-testid="stMetricValue"] { color: var(--route-text); font-weight: 720; }

        [data-testid="stFileUploader"] {
            padding: .35rem;
            border-radius: var(--route-radius-md);
            background: transparent;
        }
        [data-testid="stFileUploaderDropzone"] {
            min-height: 10rem;
            border: 1px dashed #486078;
            border-radius: var(--route-radius-md);
            background: rgba(13, 24, 37, .7);
            transition: border-color .16s ease, background .16s ease;
        }
        [data-testid="stFileUploaderDropzone"]:hover {
            border-color: var(--route-primary);
            background: rgba(86, 207, 173, .05);
        }
        [data-testid="stFileUploaderDropzone"] svg { color: var(--route-primary); }
        [data-testid="stFileUploaderDropzone"] small { color: var(--route-subtle); }

        .stButton > button, .stDownloadButton > button {
            min-height: 2.85rem;
            border-radius: var(--route-radius-sm);
            border: 1px solid var(--route-border);
            color: var(--route-text);
            background: var(--route-surface-soft);
            font-weight: 680;
            transition: transform .14s ease, border-color .14s ease, background .14s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            color: var(--route-text);
            border-color: var(--route-primary);
            background: #20364B;
            transform: translateY(-1px);
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            color: #0B1C1C;
            border-color: var(--route-primary);
            background: var(--route-primary);
            box-shadow: 0 10px 24px rgba(86, 207, 173, .14);
        }
        .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
            color: #071715;
            border-color: #72DCBE;
            background: #72DCBE;
        }

        [data-testid="stSegmentedControl"] { margin-bottom: .25rem; }
        [data-testid="stSegmentedControl"] > div { padding: .22rem; border-radius: 12px; background: #0D1825; }
        [data-testid="stSegmentedControl"] button { min-height: 2.65rem; border-radius: 9px; }
        button[data-testid="stBaseButton-segmented_controlActive"] {
            color: #0B1C1C !important;
            border-color: var(--route-primary) !important;
            background: var(--route-primary) !important;
        }
        button[data-testid="stBaseButton-segmented_controlActive"] * { color: #0B1C1C !important; }

        [data-baseweb="select"] > div, [data-baseweb="base-input"] {
            min-height: 2.8rem;
            color: var(--route-text) !important;
            border-color: var(--route-border) !important;
            border-radius: var(--route-radius-sm) !important;
            background: #152438 !important;
        }
        [data-baseweb="input"] input, [data-baseweb="select"] input,
        [data-baseweb="select"] span { color: var(--route-text) !important; }
        [data-baseweb="select"] svg, [data-baseweb="input"] svg { fill: var(--route-muted) !important; }
        [data-baseweb="popover"] > div { color: var(--route-text); background: var(--route-surface); }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: .2rem;
            padding: .28rem;
            border: 1px solid var(--route-border-soft);
            border-radius: 14px;
            background: rgba(13, 24, 37, .72);
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            height: 2.8rem;
            padding: 0 1rem;
            border-radius: 10px;
            color: var(--route-muted);
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            color: var(--route-text) !important;
            background: var(--route-surface) !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--route-primary); }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--route-border-soft);
            border-radius: var(--route-radius-md);
            overflow: hidden;
            background: var(--route-surface-soft);
        }
        [data-testid="stAlert"] {
            border-radius: var(--route-radius-md);
            border-color: var(--route-border-soft);
            background: rgba(29, 45, 64, .86);
        }
        [data-testid="stProgress"] > div > div > div { background: var(--route-primary); }
        [data-testid="stExpander"] {
            border-color: var(--route-border-soft);
            border-radius: var(--route-radius-md);
            background: rgba(23, 38, 57, .6);
        }

        @media (max-width: 1100px) {
            .app-header { align-items: flex-start; flex-direction: column; }
            .connection-status { margin-left: 4.15rem; }
        }
        @media (max-width: 768px) {
            .block-container { padding: .9rem .85rem 3rem; }
            .app-header { padding: 1.15rem; border-radius: 18px; }
            .brand-mark { width: 2.7rem; height: 2.7rem; flex-basis: 2.7rem; border-radius: 13px; }
            .brand-description { font-size: .86rem; }
            .connection-status { margin-left: 3.7rem; }
            [data-testid="stTabs"] [data-baseweb="tab"] { padding: 0 .7rem; font-size: .82rem; }
            [data-testid="stVerticalBlockBorderWrapper"] > div { padding: .9rem; }
            .section-heading { gap: .6rem; }
            div[data-testid="stMetric"] { min-height: 6.5rem; }
        }
        @media (prefers-reduced-motion: reduce) {
            html { scroll-behavior: auto; }
            *, *::before, *::after { transition: none !important; animation: none !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_svg() -> str:
    return """
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 5.5h5.5c1.8 0 2.4 1.4 3.2 3.1.7 1.5 1.4 2.8 3.2 2.8H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <path d="M5 18.5h5.2c2.3 0 2.9-1.8 3.7-3.7.7-1.6 1.5-3.3 3.6-3.3H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <circle cx="4" cy="5.5" r="1.7" fill="currentColor"/>
      <circle cx="20" cy="11.5" r="1.7" fill="currentColor"/>
      <circle cx="4" cy="18.5" r="1.7" fill="currentColor"/>
    </svg>
    """


def render_header(*, api_configured: bool) -> None:
    """Renderiza o cabeçalho institucional com um estado real da integração."""

    status_class = "" if api_configured else " pending"
    status_label = "API configurada" if api_configured else "API não configurada"
    st.markdown(
        f"""
        <header class="app-header">
          <div class="brand-lockup">
            <div class="brand-mark">{_logo_svg()}</div>
            <div>
              <div class="brand-kicker">Operações logísticas</div>
              <h1>Calculador de Rotas</h1>
              <p class="brand-description">Importação, conferência de quilometragem e análise de trajetos em um único fluxo.</p>
            </div>
          </div>
          <div class="connection-status{status_class}"><span class="status-dot"></span>{status_label}</div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(*, imported: bool, calculated: bool) -> None:
    """Exibe a identidade compacta e o progresso real da sessão."""

    st.markdown(
        f"""
        <div class="sidebar-brand">
          <div class="sidebar-mark">{_logo_svg()}</div>
          <div><strong>Calculador de Rotas</strong><span>Central de operações</span></div>
        </div>
        <div class="sidebar-label">Fluxo da operação</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="flow-step done"><span class="flow-dot">1</span><span>Definir a origem</span></div>
        <div class="flow-step {'done' if imported else ''}"><span class="flow-dot">2</span><span>Importar os dados</span></div>
        <div class="flow-step {'done' if calculated else ''}"><span class="flow-dot">3</span><span>Processar as rotas</span></div>
        <div class="flow-step {'done' if calculated else ''}"><span class="flow-dot">4</span><span>Analisar e exportar</span></div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(step: str, title: str, description: str) -> None:
    """Cria um título de seção consistente e acessível."""

    st.markdown(
        f"""
        <div class="section-heading">
          <div class="section-number">{html.escape(step)}</div>
          <div><h2>{html.escape(title)}</h2><p>{html.escape(description)}</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, description: str) -> None:
    """Exibe orientação neutra quando ainda não há dados processados."""

    st.markdown(
        f'<div class="empty-state"><strong>{html.escape(title)}</strong><span>{html.escape(description)}</span></div>',
        unsafe_allow_html=True,
    )


def render_result_callout(calculated: int) -> None:
    """Apresenta o resultado sem criar informações além das já calculadas."""

    st.markdown(
        f'<div class="result-callout"><strong>{calculated} rota(s) pronta(s) para conferência.</strong> '
        'O arquivo final inclui coordenadas, distância GPS, hodômetro, percentual de diferença e links de rota.</div>',
        unsafe_allow_html=True,
    )
