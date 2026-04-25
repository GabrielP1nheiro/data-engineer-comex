"""
Queries SQL parametrizadas para os dashboards (v0.4).

Convenções:
- Toda função pública é cacheada com ``@st.cache_data`` (TTL 5 min) — DAG é
  mensal, mas dev pode triggar manual; 5 min equilibra fresh vs latência.
- Argumentos de filtro são tuplas (hashable) — ``None`` ou ``()`` significa
  "sem filtro".
- Identificadores de schema vêm de ``lib.db`` (não hardcoded) para honrar
  o seam ``COMEX_DB_TARGET``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.db import SCHEMA_MARTS, get_connection


_CACHE_TTL = 300  # 5 minutos


# =============================================================================
# Catálogo (filtros / sidebars) — TTL maior, raramente muda
# =============================================================================

@st.cache_data(ttl=3600)
def lista_ufs() -> list[str]:
    """UFs distintas presentes na balança comercial, ordenadas."""
    con = get_connection()
    return [r[0] for r in con.execute(
        f"select distinct sg_uf from {SCHEMA_MARTS}.mart_balanca_comercial "
        f"where sg_uf is not null order by sg_uf"
    ).fetchall()]


@st.cache_data(ttl=3600)
def lista_blocos() -> list[tuple[str, str]]:
    """Lista (co_bloco, no_bloco) ordenada por nome."""
    con = get_connection()
    return [(r[0], r[1]) for r in con.execute(
        f"select distinct co_bloco, no_bloco "
        f"from {SCHEMA_MARTS}.mart_blocos_economicos "
        f"order by no_bloco"
    ).fetchall()]


@st.cache_data(ttl=3600)
def range_anos() -> tuple[int, int]:
    """Menor e maior ano cobertos pelos marts."""
    con = get_connection()
    row = con.execute(
        f"select min(ano), max(ano) from {SCHEMA_MARTS}.mart_balanca_comercial"
    ).fetchone()
    return int(row[0]), int(row[1])


# =============================================================================
# Balança Comercial
# =============================================================================

def _where_uf(ufs: tuple[str, ...] | None) -> tuple[str, list]:
    """Constrói cláusula ``and sg_uf in (...)`` se ``ufs`` for truthy."""
    if not ufs:
        return "", []
    placeholders = ",".join("?" * len(ufs))
    return f" and sg_uf in ({placeholders})", list(ufs)


@st.cache_data(ttl=_CACHE_TTL)
def balanca_kpis(
    ufs: tuple[str, ...] | None,
    ano_min: int,
    ano_max: int,
) -> dict:
    """KPIs agregados do período — saldo, corrente, # UFs com saldo positivo."""
    con = get_connection()
    where_uf, params_uf = _where_uf(ufs)
    sql = f"""
        with por_uf as (
            select sg_uf, sum(saldo_fob_usd) as saldo
            from {SCHEMA_MARTS}.mart_balanca_comercial
            where ano between ? and ?{where_uf}
            group by sg_uf
        )
        select
            sum(saldo) as saldo_total,
            (select sum(corrente_comercio_usd)
                from {SCHEMA_MARTS}.mart_balanca_comercial
                where ano between ? and ?{where_uf}) as corrente_total,
            count(*) filter (where saldo > 0) as ufs_positivas,
            count(*) as ufs_total
        from por_uf
    """
    params = [ano_min, ano_max, *params_uf, ano_min, ano_max, *params_uf]
    row = con.execute(sql, params).fetchone()
    return {
        "saldo_total": row[0],
        "corrente_total": row[1],
        "ufs_positivas": row[2],
        "ufs_total": row[3],
    }


@st.cache_data(ttl=_CACHE_TTL)
def balanca_serie_mensal(
    ufs: tuple[str, ...] | None,
    ano_min: int,
    ano_max: int,
) -> pd.DataFrame:
    """Série temporal mensal — exp, imp, saldo, corrente."""
    con = get_connection()
    where_uf, params_uf = _where_uf(ufs)
    sql = f"""
        select data_ref,
               sum(vl_exp_fob_usd)        as exp_usd,
               sum(vl_imp_fob_usd)        as imp_usd,
               sum(saldo_fob_usd)         as saldo_usd,
               sum(corrente_comercio_usd) as corrente_usd
        from {SCHEMA_MARTS}.mart_balanca_comercial
        where ano between ? and ?{where_uf}
        group by data_ref
        order by data_ref
    """
    return con.execute(sql, [ano_min, ano_max, *params_uf]).df()


@st.cache_data(ttl=_CACHE_TTL)
def balanca_top_ufs(
    ufs: tuple[str, ...] | None,
    ano_min: int,
    ano_max: int,
    top_n: int = 10,
) -> pd.DataFrame:
    """Top N UFs por saldo no período (ordenado decrescente)."""
    con = get_connection()
    where_uf, params_uf = _where_uf(ufs)
    sql = f"""
        select sg_uf,
               sum(vl_exp_fob_usd) as exp_usd,
               sum(vl_imp_fob_usd) as imp_usd,
               sum(saldo_fob_usd)  as saldo_usd
        from {SCHEMA_MARTS}.mart_balanca_comercial
        where ano between ? and ?{where_uf}
        group by sg_uf
        order by saldo_usd desc
        limit ?
    """
    return con.execute(sql, [ano_min, ano_max, *params_uf, top_n]).df()


@st.cache_data(ttl=_CACHE_TTL)
def balanca_detalhe(
    ufs: tuple[str, ...] | None,
    ano_min: int,
    ano_max: int,
) -> pd.DataFrame:
    """Detalhamento por UF/ano — para tabela e download CSV."""
    con = get_connection()
    where_uf, params_uf = _where_uf(ufs)
    sql = f"""
        select ano,
               sg_uf,
               sum(vl_exp_fob_usd)        as exp_usd,
               sum(vl_imp_fob_usd)        as imp_usd,
               sum(saldo_fob_usd)         as saldo_usd,
               sum(corrente_comercio_usd) as corrente_usd
        from {SCHEMA_MARTS}.mart_balanca_comercial
        where ano between ? and ?{where_uf}
        group by ano, sg_uf
        order by ano, saldo_usd desc
    """
    return con.execute(sql, [ano_min, ano_max, *params_uf]).df()


# =============================================================================
# Top Produtos
# =============================================================================

@st.cache_data(ttl=_CACHE_TTL)
def top_produtos(direcao: str, ano: int, top_n: int) -> pd.DataFrame:
    """Top N NCMs por valor FOB para uma direção (EXP|IMP) e ano."""
    con = get_connection()
    sql = f"""
        select co_ncm,
               no_ncm_pt,
               co_sh2,
               no_sh2_pt,
               vl_fob_usd,
               kg_liquido,
               share_direcao_ano,
               rank_ano_direcao
        from {SCHEMA_MARTS}.mart_top_produtos
        where direcao = ? and ano = ? and rank_ano_direcao <= ?
        order by rank_ano_direcao
    """
    return con.execute(sql, [direcao, ano, top_n]).df()


@st.cache_data(ttl=_CACHE_TTL)
def top_sh2(direcao: str, ano: int) -> pd.DataFrame:
    """Agregação por capítulo SH2 — alimenta o treemap."""
    con = get_connection()
    sql = f"""
        select co_sh2,
               no_sh2_pt,
               sum(vl_fob_usd) as vl_fob_usd
        from {SCHEMA_MARTS}.mart_top_produtos
        where direcao = ? and ano = ?
        group by co_sh2, no_sh2_pt
        having sum(vl_fob_usd) > 0
        order by vl_fob_usd desc
    """
    return con.execute(sql, [direcao, ano]).df()


# =============================================================================
# Blocos Econômicos
# =============================================================================

def _where_blocos(blocos: tuple[str, ...] | None) -> tuple[str, list]:
    """Constrói cláusula ``and co_bloco in (...)`` se ``blocos`` for truthy."""
    if not blocos:
        return "", []
    placeholders = ",".join("?" * len(blocos))
    return f" and co_bloco in ({placeholders})", list(blocos)


@st.cache_data(ttl=_CACHE_TTL)
def blocos_serie_anual(
    blocos: tuple[str, ...] | None,
    direcao: str,
) -> pd.DataFrame:
    """Série anual por bloco econômico para uma direção (EXP|IMP)."""
    con = get_connection()
    where_b, params_b = _where_blocos(blocos)
    sql = f"""
        select ano,
               no_bloco,
               sum(vl_fob_usd) as vl_fob_usd
        from {SCHEMA_MARTS}.mart_blocos_economicos
        where direcao = ?{where_b}
        group by ano, no_bloco
        order by ano, no_bloco
    """
    return con.execute(sql, [direcao, *params_b]).df()


@st.cache_data(ttl=_CACHE_TTL)
def blocos_share_anual(direcao: str) -> pd.DataFrame:
    """
    Share de cada bloco no total anual da direção — para barras empilhadas.

    NOTA: como um país pode pertencer a múltiplos blocos, o share aqui é
    relativo ao TOTAL DE LINHAS DO MART (com sobreposição), não ao volume
    total real. É uma visão de "peso de cada bloco no agregado", útil pra
    comparar tamanhos relativos, mas não é uma decomposição mutuamente
    exclusiva. O banner na página deixa isso explícito.
    """
    con = get_connection()
    sql = f"""
        with por_bloco as (
            select ano, no_bloco, sum(vl_fob_usd) as vl_fob_usd
            from {SCHEMA_MARTS}.mart_blocos_economicos
            where direcao = ?
            group by ano, no_bloco
        ),
        total_ano as (
            select ano, sum(vl_fob_usd) as total
            from por_bloco
            group by ano
        )
        select p.ano,
               p.no_bloco,
               p.vl_fob_usd,
               p.vl_fob_usd / t.total as share_ano
        from por_bloco p
        join total_ano t using (ano)
        order by p.ano, p.no_bloco
    """
    return con.execute(sql, [direcao]).df()


@st.cache_data(ttl=_CACHE_TTL)
def blocos_detalhe(
    blocos: tuple[str, ...] | None,
    direcao: str,
) -> pd.DataFrame:
    """Detalhamento bloco/ano/mês — para tabela e download."""
    con = get_connection()
    where_b, params_b = _where_blocos(blocos)
    sql = f"""
        select ano,
               mes,
               no_bloco,
               direcao,
               sum(vl_fob_usd) as vl_fob_usd,
               sum(kg_liquido) as kg_liquido
        from {SCHEMA_MARTS}.mart_blocos_economicos
        where direcao = ?{where_b}
        group by ano, mes, no_bloco, direcao
        order by ano, mes, vl_fob_usd desc
    """
    return con.execute(sql, [direcao, *params_b]).df()
