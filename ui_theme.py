"""Apresentação da interface aprovada, sem dependências do motor de rotas."""
from pathlib import Path

import streamlit as st


def apply_theme(light: bool) -> None:
    # Tokens compartilhados permitem alternar o tema sem duplicar o layout.
    palette = (
        ("#f5f7fb", "#ffffff", "#f0f4fa", "#d5deeb", "#172238", "#58677e", "#2563eb", "#eaf1ff")
        if light else
        ("#090d15", "#101722", "#151e2c", "#253044", "#edf2fb", "#a1aec3", "#3b82f6", "#132745")
    )
    tokens = dict(zip(("bg", "panel", "raised", "border", "text", "muted", "blue", "soft"), palette))
    variables = ";".join(f"--rp-{name}:{value}" for name, value in tokens.items())
    css = (Path(__file__).parent / "assets" / "interface.css").read_text(encoding="utf-8")
    st.markdown(f"<style>:root{{{variables}}}{css}</style>", unsafe_allow_html=True)


def render_guide() -> None:
    st.markdown('''
    <aside class="rp-guide"><h3>Como funciona</h3>
      <div class="rp-step"><span>01</span><div><strong>Envie o arquivo</strong><p>Uma planilha com origem e destino de cada rota.</p></div></div>
      <div class="rp-step"><span>02</span><div><strong>Calcule as rotas</strong><p>Acompanhe as consultas e o andamento.</p></div></div>
      <div class="rp-step"><span>03</span><div><strong>Baixe e analise</strong><p>Distâncias, status e links no arquivo final.</p></div></div>
    </aside>''', unsafe_allow_html=True)


def render_analysis_empty() -> None:
    st.markdown('''
    <div class="rp-analysis">
      <div class="rp-symbol" aria-hidden="true">▥</div>
      <h3>Uma visão clara de cada rota.</h3>
      <p>Depois de calcular sua planilha, consulte aqui as distâncias, os filtros e os relatórios.</p>
      <span>Nenhum dado foi carregado. Comece pela aba Calcular rotas.</span>
    </div>''', unsafe_allow_html=True)
