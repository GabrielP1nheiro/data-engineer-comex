{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- mart_exportacoes_por_estado
--
-- Valor exportado FOB por ano, mês e UF + participação (%) no total do mês.
-- Window function calcula o share sem precisar de CTE adicional.
--
-- Grão: (ano, mes, sg_uf)
-- =============================================================================

with por_uf as (
    select
        ano,
        mes,
        data_ref,
        sg_uf,
        sum(vl_fob_usd)  as vl_fob_usd,
        sum(kg_liquido)  as kg_liquido
    from {{ ref('core_comercio') }}
    where direcao = 'EXP'
    group by 1, 2, 3, 4
)

select
    ano,
    mes,
    data_ref,
    sg_uf,
    vl_fob_usd,
    kg_liquido,
    -- Participação da UF no total do mês
    vl_fob_usd
        / nullif(sum(vl_fob_usd) over (partition by ano, mes), 0)
        as share_nacional_mes,
    -- Ranking da UF no mês (1 = maior exportador)
    rank() over (partition by ano, mes order by vl_fob_usd desc) as rank_mes
from por_uf
