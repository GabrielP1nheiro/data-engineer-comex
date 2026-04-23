{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- mart_balanca_comercial
--
-- Balança comercial por ano, mês e UF. Saldo = exportações FOB − importações
-- FOB (padrão BACEN usa FOB nos dois lados para medir balança).
--
-- Use este mart para responder:
--   1. "Qual a balança comercial do Brasil por estado nos últimos 5 anos?"
--   5. "Como a pandemia (2020) impactou o comércio exterior brasileiro?"
--
-- Grão: (ano, mes, sg_uf)
-- =============================================================================

with comercio as (
    select
        ano,
        mes,
        data_ref,
        sg_uf,
        direcao,
        vl_fob_usd
    from {{ ref('core_comercio') }}
),

agregado as (
    select
        ano,
        mes,
        data_ref,
        sg_uf,
        sum(case when direcao = 'EXP' then vl_fob_usd else 0 end)  as vl_exp_fob_usd,
        sum(case when direcao = 'IMP' then vl_fob_usd else 0 end)  as vl_imp_fob_usd
    from comercio
    group by 1, 2, 3, 4
)

select
    ano,
    mes,
    data_ref,
    sg_uf,
    vl_exp_fob_usd,
    vl_imp_fob_usd,
    vl_exp_fob_usd - vl_imp_fob_usd  as saldo_fob_usd,
    -- Fluxo total (utilizado em alguns indicadores de corrente de comércio)
    vl_exp_fob_usd + vl_imp_fob_usd  as corrente_comercio_usd
from agregado
