{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_urf
--
-- Unidades da Receita Federal (URF) de embarque/desembarque.
-- CO_URF tem 7 dígitos no padrão MDIC — LPAD preserva zeros à esquerda.
-- =============================================================================

with fonte as (
    select * from {{ source('comex_aux', 'urf') }}
)

select
    lpad(cast(CO_URF as varchar), 7, '0')  as co_urf,
    cast(NO_URF as varchar)                as no_urf
from fonte
