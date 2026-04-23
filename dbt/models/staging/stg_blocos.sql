{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_blocos
--
-- Relação país x bloco econômico. Um país pode pertencer a múltiplos blocos
-- (ex: Alemanha -> União Europeia + OCDE), por isso NÃO há unicidade em
-- co_pais — a chave composta é (co_pais, co_bloco).
-- =============================================================================

with fonte as (
    select * from {{ source('comex_aux', 'pais_bloco') }}
)

select
    lpad(cast(CO_PAIS  as varchar), 3, '0')  as co_pais,
    cast(CO_BLOCO as varchar)                as co_bloco,
    cast(NO_BLOCO as varchar)                as no_bloco
from fonte
