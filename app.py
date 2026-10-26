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
from ui_theme import (
    apply_theme,
    render_empty_state,
    render_header,
    render_result_callout,
    render_section_header,
    render_sidebar,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
st.set_page_config(
    page_title="Calculador de Rotas",
    page_icon=":material/route:",
    layout="wide",
    initial_sidebar_state="expanded",
)


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


token, category_id, timezone_name, item_mapping = _checklist_settings()
light_mode = False
apply_theme()
render_header(api_configured=bool(token))

with st.sidebar:
    imported = "api_import" in st.session_state or "upload_token" in st.session_state
    calculated = "result" in st.session_state
    render_sidebar(imported=imported, calculated=calculated)

route_tab, map_tab, analysis_tab = st.tabs(["Operação", "Mapa de rotas", "Indicadores"])

with route_tab:
    with st.container(border=True):
        render_section_header(
            "01",
            "Escolha a origem dos dados",
            "Importe diretamente do Checklist Fácil ou processe uma planilha Excel já existente.",
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
        render_section_header(
            "02",
            "Importe e processe a planilha",
            "Selecione um arquivo XLSX de até 25 MB. A validação ocorre antes do cálculo das rotas.",
        )
        uploaded_file = st.file_uploader(
            "Envie uma planilha Excel (.xlsx)",
            type=["xlsx"],
            max_upload_size=25,
            help="O arquivo precisa conter as coordenadas inicial e final na primeira linha da aba ativa.",
        )

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
        try:
            now = datetime.now(ZoneInfo(timezone_name))
        except Exception:
            timezone_name = DEFAULT_TIMEZONE
            now = datetime.now(ZoneInfo(timezone_name))

        render_section_header(
            "02",
            "Defina o período da consulta",
            "Somente checklists concluídos serão importados; as rotas válidas serão calculadas em lote.",
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
        render_section_header(
            "03",
            "Resultados e exportação",
            "Confira os indicadores da execução e baixe o arquivo final para análise.",
        )
        coverage = (result.calculated / result.total * 100) if result.total else 0
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de rotas", result.total)
        col2.metric("Calculadas", result.calculated)
        col3.metric("Não calculadas", result.failed)
        col4.metric("Taxa de sucesso", f"{coverage:.1f}%")
        render_result_callout(result.calculated)
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
        render_empty_state(
            "Indicadores ainda não disponíveis",
            "Conclua o processamento na aba Operação para visualizar as análises.",
        )
    else:
        render_section_header(
            "03",
            "Indicadores da operação",
            "Analise quilometragem, produtividade, divergências e qualidade dos dados processados.",
        )
        render_dashboard(st.session_state["processed_df"], st.session_state["original_name"], light_mode)

with map_tab:
    if "processed_df" not in st.session_state:
        render_empty_state(
            "Mapa aguardando rotas",
            "Conclua o processamento na aba Operação para explorar os trajetos.",
        )
    else:
        render_route_map(st.session_state["processed_df"], light_mode)
