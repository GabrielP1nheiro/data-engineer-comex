{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_uf
--
-- Unidades Federativas do Brasil.
-- Os dados transacionais usam SG_UF_NCM (sigla, ex: 'SP', 'RJ'), então
-- a chave natural de join é SG_UF, não CO_UF.
-- =============================================================================

with fonte as (
    select * from {{ source('comex_aux', 'uf') }}
)

select
    cast(SG_UF     as varchar)  as sg_uf,
    cast(CO_UF     as varchar)  as co_uf,
    cast(NO_UF     as varchar)  as no_uf,
    cast(NO_REGIAO as varchar)  as no_regiao
from fonte
