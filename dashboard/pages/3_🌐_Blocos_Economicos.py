"""
Blocos Econômicos — comércio por bloco (Mercosul, UE, Ásia, etc).

Filtros: multiselect de bloco + direção (EXP|IMP).
Charts: série temporal anual por bloco + share de cada bloco no agregado anual.
Banner explica que um país pode pertencer a múltiplos blocos.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.charts import (
    CATEGORICAL_SEQUENCE,
    PALETTE,
    base_layout,
    fmt_pct,
    fmt_usd_bi,
)
from lib.db import warehouse_exists
from lib.queries import blocos_detalhe, blocos_serie_anual, blocos_share_anual, lista_blocos


st.set_page_config(
    page_title="Blocos Econômicos — Comex Brasil",
    page_icon="🌐",
    layout="wide",
)


if not warehouse_exists():
    st.error("Warehouse não encontrado — volte à página inicial.")
    st.stop()


st.title("🌐 Blocos Econômicos")
st.caption(
    "Volume comercializado por bloco econômico. "
    "Valores em FOB (US$)."
)

st.info(
    "**Atenção:** um mesmo país pode pertencer a **múltiplos blocos** "
    "(ex: a Alemanha está em UE, OCDE e G20). Por isso, **não some o "
    "agregado de blocos diferentes** como se fosse o total do Brasil — "
    "compare blocos entre si, ou filtre um bloco específico."
)


# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------
blocos_disponiveis = lista_blocos()  # list[(co_bloco, no_bloco)]
mapa_no_para_co = {no: co for co, no in blocos_disponiveis}

with st.sidebar:
    st.header("Filtros")

    direcao = st.radio(
        "Direção",
        options=["EXP", "IMP"],
        format_func=lambda d: "Exportações" if d == "EXP" else "Importações",
        horizontal=True,
    )

    nomes_sel = st.multiselect(
        "Blocos",
        options=[no for _, no in blocos_disponiveis],
        default=[],
        placeholder="Todos os blocos",
        help="Vazio = todos os blocos",
    )

    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


blocos_filter = tuple(mapa_no_para_co[n] for n in nomes_sel) if nomes_sel else None
label_direcao = "Exportações" if direcao == "EXP" else "Importações"


# -----------------------------------------------------------------------------
# Chart 1 — série anual por bloco
# -----------------------------------------------------------------------------
st.subheader(f"Evolução anual — {label_direcao}")

df_anual = blocos_serie_anual(blocos_filter, direcao)

if df_anual.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    df_anual["vl_bi"] = df_anual["vl_fob_usd"] / 1e9
    fig = px.line(
        df_anual,
        x="ano",
        y="vl_bi",
        color="no_bloco",
        markers=True,
        color_discrete_sequence=CATEGORICAL_SEQUENCE,
    )
    fig.update_layout(**base_layout(height=420))
    fig.update_xaxes(title_text=None, dtick=1, gridcolor="#E9ECEF")
    fig.update_yaxes(title_text="US$ bilhões", gridcolor="#E9ECEF")
    fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.2f} bi US$<extra></extra>")
    fig.update_layout(legend_title_text="Bloco")
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Chart 2 — share por bloco (barras empilhadas)
# -----------------------------------------------------------------------------
st.subheader(f"Peso relativo de cada bloco — {label_direcao}")
st.caption(
    "Share calculado sobre a soma das linhas do mart por ano "
    "(com sobreposição entre blocos). Útil para comparar tamanhos relativos, "
    "não como decomposição mutuamente exclusiva."
)

df_share = blocos_share_anual(direcao)

if df_share.empty:
    st.info("Sem dados.")
else:
    df_share["share_pct"] = df_share["share_ano"] * 100
    fig = px.bar(
        df_share,
        x="ano",
        y="share_pct",
        color="no_bloco",
        color_discrete_sequence=CATEGORICAL_SEQUENCE,
    )
    fig.update_layout(**base_layout(height=420))
    fig.update_layout(barmode="stack", legend_title_text="Bloco")
    fig.update_xaxes(title_text=None, dtick=1)
    fig.update_yaxes(title_text="Share (%)", ticksuffix="%", gridcolor="#E9ECEF")
    fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Tabela + download
# -----------------------------------------------------------------------------
st.subheader("Detalhamento por bloco / mês")

df_detalhe = blocos_detalhe(blocos_filter, direcao)

if df_detalhe.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    df_show = df_detalhe.rename(columns={
        "ano": "Ano",
        "mes": "Mês",
        "no_bloco": "Bloco",
        "direcao": "Direção",
        "vl_fob_usd": "FOB (US$)",
        "kg_liquido": "Peso líq. (kg)",
    })
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    csv = df_detalhe.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Baixar CSV",
        data=csv,
        file_name=f"blocos_economicos_{direcao}.csv",
        mime="text/csv",
    )
