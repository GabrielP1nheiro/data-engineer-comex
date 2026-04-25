"""
Top Produtos — ranking de NCMs por valor FOB com hierarquia SH.

Filtros: direção (EXP|IMP), ano único, top-N.
Charts: barras horizontais top NCMs + treemap por capítulo SH2.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.charts import PALETTE, base_layout, fmt_usd_bi, fmt_pct
from lib.db import warehouse_exists
from lib.queries import range_anos, top_produtos, top_sh2


st.set_page_config(
    page_title="Top Produtos — Comex Brasil",
    page_icon="🏆",
    layout="wide",
)


if not warehouse_exists():
    st.error("Warehouse não encontrado — volte à página inicial.")
    st.stop()


st.title("🏆 Top Produtos")
st.caption(
    "Ranking de NCMs (Nomenclatura Comum do Mercosul) por valor FOB. "
    "Um mesmo NCM pode aparecer em EXP e IMP — não é duplicação "
    "(ex: petróleo NCM 27090010 é exportado e importado simultaneamente)."
)


# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------
ano_min_db, ano_max_db = range_anos()

with st.sidebar:
    st.header("Filtros")

    direcao = st.radio(
        "Direção",
        options=["EXP", "IMP"],
        format_func=lambda d: "Exportações" if d == "EXP" else "Importações",
        horizontal=True,
    )

    ano_sel = st.slider(
        "Ano",
        min_value=ano_min_db,
        max_value=ano_max_db,
        value=ano_max_db,
    )

    top_n = st.slider(
        "Quantidade no ranking",
        min_value=5,
        max_value=50,
        value=15,
        step=5,
    )

    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


cor_direcao = PALETTE["exp"] if direcao == "EXP" else PALETTE["imp"]
label_direcao = "Exportações" if direcao == "EXP" else "Importações"


# -----------------------------------------------------------------------------
# Chart 1 — barras horizontais com top-N NCMs
# -----------------------------------------------------------------------------
st.subheader(f"Top {top_n} NCMs — {label_direcao} {ano_sel}")

df_top = top_produtos(direcao, ano_sel, top_n)

if df_top.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    # Trunca descrição para não estourar o eixo Y
    df_top["label"] = df_top.apply(
        lambda r: f"{r['co_ncm']} — {r['no_ncm_pt'][:55]}"
        + ("…" if len(r["no_ncm_pt"]) > 55 else ""),
        axis=1,
    )
    df_sorted = df_top.sort_values("vl_fob_usd")  # asc para barra horizontal

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_sorted["vl_fob_usd"] / 1e9,
        y=df_sorted["label"],
        orientation="h",
        marker={"color": cor_direcao},
        text=[fmt_usd_bi(v) for v in df_sorted["vl_fob_usd"]],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Valor: %{customdata}<extra></extra>",
        customdata=[fmt_usd_bi(v) for v in df_sorted["vl_fob_usd"]],
    ))
    fig.update_layout(**base_layout(height=max(380, 22 * top_n)))
    fig.update_xaxes(title_text="US$ bilhões", gridcolor="#E9ECEF")
    fig.update_yaxes(title_text=None, automargin=True)
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Chart 2 — treemap por SH2 (capítulo)
# -----------------------------------------------------------------------------
st.subheader(f"Distribuição por capítulo SH2 — {label_direcao} {ano_sel}")
st.caption(
    "SH2 é o primeiro nível da hierarquia do Sistema Harmonizado "
    "(2 dígitos, ~99 capítulos). Tamanho do bloco = valor FOB total."
)

df_sh2 = top_sh2(direcao, ano_sel)

if df_sh2.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    df_sh2["label"] = df_sh2["co_sh2"] + " — " + df_sh2["no_sh2_pt"]
    fig = px.treemap(
        df_sh2,
        path=["label"],
        values="vl_fob_usd",
        color="vl_fob_usd",
        color_continuous_scale=(
            "Greens" if direcao == "EXP" else "Reds"
        ),
        custom_data=["co_sh2", "no_sh2_pt", "vl_fob_usd"],
    )
    fig.update_traces(
        hovertemplate=(
            "<b>SH2 %{customdata[0]}</b> — %{customdata[1]}"
            "<br>Valor: US$ %{customdata[2]:,.0f}<extra></extra>"
        ),
        textinfo="label+percent parent",
    )
    fig.update_layout(**base_layout(height=500))
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# Tabela + download
# -----------------------------------------------------------------------------
if not df_top.empty:
    st.subheader("Detalhamento")
    df_show = df_top[[
        "rank_ano_direcao", "co_ncm", "no_ncm_pt",
        "co_sh2", "no_sh2_pt", "vl_fob_usd",
        "kg_liquido", "share_direcao_ano",
    ]].rename(columns={
        "rank_ano_direcao": "Rank",
        "co_ncm": "NCM",
        "no_ncm_pt": "Descrição",
        "co_sh2": "SH2",
        "no_sh2_pt": "Capítulo SH2",
        "vl_fob_usd": "FOB (US$)",
        "kg_liquido": "Peso líq. (kg)",
        "share_direcao_ano": "Share da direção",
    })
    df_show["Share da direção"] = df_show["Share da direção"].apply(fmt_pct)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    csv = df_top.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Baixar CSV",
        data=csv,
        file_name=f"top_produtos_{direcao}_{ano_sel}_top{top_n}.csv",
        mime="text/csv",
    )
