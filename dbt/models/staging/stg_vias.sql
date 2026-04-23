{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_vias
--
-- Vias de transporte (marítima, aérea, rodoviária, ferroviária, etc).
-- CO_VIA não costuma exigir LPAD (nos transacionais vem sem zero à esquerda).
-- =============================================================================

with fonte as (
    select * from {{ source('comex_aux', 'via') }}
)

select
    cast(CO_VIA as varchar)  as co_via,
    cast(NO_VIA as varchar)  as no_via
from fonte
