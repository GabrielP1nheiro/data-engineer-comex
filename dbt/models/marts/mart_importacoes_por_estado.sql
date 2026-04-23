{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- mart_importacoes_por_estado
--
-- Valor importado (FOB e CIF) por ano, mês e UF + participação no total.
-- Mantemos as duas métricas: FOB para comparabilidade com exportações;
-- CIF para análises de custo real pago pelos importadores.
--
-- Grão: (ano, mes, sg_uf)
-- =============================================================================

with por_uf as (
    select
        ano,
        mes,
        data_ref,
        sg_uf,
        sum(vl_fob_usd)   as vl_fob_usd,
        sum(vl_cif_usd)   as vl_cif_usd,
        sum(kg_liquido)   as kg_liquido
    from {{ ref('core_comercio') }}
    where direcao = 'IMP'
    group by 1, 2, 3, 4
)

select
    ano,
    mes,
    data_ref,
    sg_uf,
    vl_fob_usd,
    vl_cif_usd,
    kg_liquido,
    vl_fob_usd
        / nullif(sum(vl_fob_usd) over (partition by ano, mes), 0)
        as share_nacional_mes,
    rank() over (partition by ano, mes order by vl_fob_usd desc) as rank_mes
from por_uf
