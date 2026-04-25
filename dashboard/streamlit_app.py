"""
Comex Brasil — Dashboards (v0.4).

Página inicial: status do warehouse e índice dos dashboards.
Páginas detalhadas vivem em ``pages/`` (multipage nativo do Streamlit).
"""

from __future__ import annotations

import streamlit as st

from lib.db import (
    DB_TARGET,
    DUCKDB_PATH,
    SCHEMA_CORE,
    get_connection,
    warehouse_exists,
    warehouse_mtime,
)


st.set_page_config(
    page_title="Comex Brasil — Dashboards",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.title("🇧🇷 Comex Brasil — Dashboards")
st.caption(
    "Análise de comércio exterior brasileiro a partir de dados públicos do MDIC. "
    "Use o menu lateral para navegar entre os dashboards."
)


if not warehouse_exists():
    st.error(
        f"**Warehouse não encontrado.** Esperado em `{DUCKDB_PATH}`.\n\n"
        "Rode a DAG `comex_pipeline` no Airflow (http://localhost:8080) "
        "para popular o DuckDB com os dados do MDIC."
    )
    st.stop()


@st.cache_data(ttl=60)
def status_warehouse() -> dict:
    con = get_connection()
    rows_core = con.execute(
        f"select count(*) from {SCHEMA_CORE}.core_comercio"
    ).fetchone()[0]
    ano_min, ano_max = con.execute(
        f"select min(ano), max(ano) from {SCHEMA_CORE}.core_comercio"
    ).fetchone()
    return {
        "rows_core": rows_core,
        "ano_min": ano_min,
        "ano_max": ano_max,
        "mtime": warehouse_mtime(),
        "target": DB_TARGET,
    }


try:
    status = status_warehouse()
except Exception as exc:
    st.error(f"Falha ao consultar o warehouse: {exc}")
    st.stop()


col1, col2, col3, col4 = st.columns(4)
col1.metric("Backend", status["target"].upper())
col2.metric(
    "Linhas em core_comercio",
    f"{status['rows_core']:,}".replace(",", "."),
)
col3.metric("Cobertura", f"{status['ano_min']} – {status['ano_max']}")
col4.metric("Última atualização", status["mtime"] or "—")


st.divider()


st.subheader("Dashboards disponíveis")
st.markdown(
    """
- 📊 **Balança Comercial** — saldo, exportações e importações por UF e período
- 🏆 **Top Produtos** — ranking de NCMs por valor FOB com hierarquia SH
- 🌐 **Blocos Econômicos** — comércio por bloco (Mercosul, UE, Ásia, etc.)
"""
)


with st.sidebar:
    st.header("Sobre")
    st.markdown(
        "Pipeline end-to-end de Data Engineering sobre dados do MDIC.\n\n"
        "**Stack:** Airflow + dbt + DuckDB + Streamlit.\n\n"
        f"**Warehouse:** `{DB_TARGET}` (somente leitura)."
    )
    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
