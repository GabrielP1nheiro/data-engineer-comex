"""
Balança Comercial — saldo, exportações e importações por UF e período.

Filtros (sidebar): multiselect de UF + slider de range de anos.
Charts: série temporal mensal (linhas) + top 10 UFs por saldo (barras).
Tabela detalhada com download CSV.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from lib.charts import PALETTE, base_layout, fmt_usd_bi
from lib.db import warehouse_exists
from lib.queries import (
    balanca_detalhe,
    balanca_kpis,
    balanca_serie_mensal,
    balanca_top_ufs,
    lista_ufs,
    range_anos,
)


st.set_page_config(
    page_title="Balança Comercial — Comex Brasil",
    page_icon="📊",
    layout="wide",
)


if not warehouse_exists():
    st.error("Warehouse não encontrado — volte à página inicial.")
    st.stop()


st.title("📊 Balança Comercial")
st.caption(
    "Saldo (exportações − importações) por UF e período. "
    "Valores em FOB (US$)."
)


# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------
ano_min_db, ano_max_db = range_anos()
ufs_disponiveis = lista_ufs()

with st.sidebar:
    st.header("Filtros")

    anos_sel = st.slider(
        "Período (anos)",
        min_value=ano_min_db,
        max_value=ano_max_db,
        value=(ano_min_db, ano_max_db),
    )

    ufs_sel = st.multiselect(
        "UFs",
        options=ufs_disponiveis,
        default=[],
        placeholder="Todas as UFs",
        help="Vazio = todas as UFs",
    )

    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


ufs_filter = tuple(ufs_sel) if ufs_sel else None


# -----------------------------------------------------------------------------
# KPIs
# -----------------------------------------------------------------------------
kpis = balanca_kpis(ufs_filter, anos_sel[0], anos_sel[1])

col1, col2, col3 = st.columns(3)
col1.metric("Saldo do período", fmt_usd_bi(kpis["saldo_total"]))
col2.metric("Corrente de comércio", fmt_usd_bi(kpis["corrente_total"]))
col3.metric(
    "UFs com saldo positivo",
    f"{kpis['ufs_positivas']} / {kpis['ufs_total']}",
)


st.divider()


# -----------------------------------------------------------------------------
# Chart 1 — série temporal mensal
# -----------------------------------------------------------------------------
st.subheader("Evolução mensal")

df_mensal = balanca_serie_mensal(ufs_filter, anos_sel[0], anos_sel[1])

if df_mensal.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_mensal["data_ref"], y=df_mensal["exp_usd"] / 1e9,
        mode="lines", name="Exportações",
        line={"color": PALETTE["exp"], "width": 2},
    ))
    fig.add_trace(go.Scatter(
        x=df_mensal["data_ref"], y=df_mensal["imp_usd"] / 1e9,
        mode="lines", name="Importações",
        line={"color": PALETTE["imp"], "width": 2},
    ))
    fig.add_trace(go.Scatter(
        x=df_mensal["data_ref"], y=df_mensal["saldo_usd"] / 1e9,
        mode="lines", name="Saldo",
        line={"color": PALETTE["saldo"], "width": 2, "dash": "dot"},
    ))
    fig.update_layout(**base_layout(height=400))
    fig.update_yaxes(title_text="US$ bilhões", gridcolor="#E9ECEF")
    fig.update_xaxes(title_text=None, gridcolor="#E9ECEF")
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Chart 2 — top UFs por saldo
# -----------------------------------------------------------------------------
st.subheader("Top 10 UFs por saldo no período")

df_top = balanca_top_ufs(ufs_filter, anos_sel[0], anos_sel[1], top_n=10)

if df_top.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    df_top_sorted = df_top.sort_values("saldo_usd")  # asc para barras horizontais
    cores = [
        PALETTE["exp"] if v >= 0 else PALETTE["imp"]
        for v in df_top_sorted["saldo_usd"]
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_top_sorted["saldo_usd"] / 1e9,
        y=df_top_sorted["sg_uf"],
        orientation="h",
        marker={"color": cores},
        text=[fmt_usd_bi(v) for v in df_top_sorted["saldo_usd"]],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(**base_layout(height=420))
    fig.update_xaxes(title_text="Saldo (US$ bilhões)", gridcolor="#E9ECEF")
    fig.update_yaxes(title_text=None)
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Tabela + download
# -----------------------------------------------------------------------------
st.subheader("Detalhamento por UF e ano")

df_detalhe = balanca_detalhe(ufs_filter, anos_sel[0], anos_sel[1])

if df_detalhe.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    df_show = df_detalhe.rename(columns={
        "ano": "Ano",
        "sg_uf": "UF",
        "exp_usd": "Exportações (US$)",
        "imp_usd": "Importações (US$)",
        "saldo_usd": "Saldo (US$)",
        "corrente_usd": "Corrente (US$)",
    })
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    csv = df_detalhe.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Baixar CSV",
        data=csv,
        file_name=f"balanca_comercial_{anos_sel[0]}_{anos_sel[1]}.csv",
        mime="text/csv",
    )
