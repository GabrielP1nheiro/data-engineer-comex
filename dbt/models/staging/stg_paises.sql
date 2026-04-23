{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_paises
--
-- Países e códigos. CO_PAIS é o código interno do MDIC (3 dígitos).
-- CO_PAIS_ISON3 é o código numérico ISO 3166-1 (também 3 dígitos).
-- CO_PAIS_ISOA3 é a sigla ISO alpha-3 (ex: 'BRA', 'USA').
-- =============================================================================

with fonte as (
    select * from {{ source('comex_aux', 'pais') }}
)

select
    lpad(cast(CO_PAIS       as varchar), 3, '0')  as co_pais,
    lpad(cast(CO_PAIS_ISON3 as varchar), 3, '0')  as co_pais_ison3,
    cast(CO_PAIS_ISOA3 as varchar)                as co_pais_isoa3,
    cast(NO_PAIS       as varchar)                as no_pais,
    cast(NO_PAIS_ING   as varchar)                as no_pais_en,
    cast(NO_PAIS_ESP   as varchar)                as no_pais_es
from fonte
