{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_ncm
--
-- NCM de 8 dígitos com descrição em português + hierarquia SH
-- (capítulo SH2, posição SH4, subposição SH6) enriquecida com descrições
-- vindas da tabela NCM_SH.parquet.
--
-- CO_NCM e CO_SH* vêm como BIGINT no Parquet — precisam de LPAD para
-- preservar zeros à esquerda e permitir joins corretos com as transacionais.
-- =============================================================================

with ncm as (
    select
        lpad(cast(CO_NCM  as varchar), 8, '0')    as co_ncm,
        lpad(cast(CO_SH6  as varchar), 6, '0')    as co_sh6,
        cast(CO_UNID as varchar)                  as co_unid,
        cast(NO_NCM_POR as varchar)               as no_ncm_pt
    from {{ source('comex_aux', 'ncm') }}
),

sh as (
    select
        lpad(cast(CO_SH6 as varchar), 6, '0')     as co_sh6,
        lpad(cast(CO_SH4 as varchar), 4, '0')     as co_sh4,
        lpad(cast(CO_SH2 as varchar), 2, '0')     as co_sh2,
        cast(NO_SH6_POR as varchar)               as no_sh6_pt,
        cast(NO_SH4_POR as varchar)               as no_sh4_pt,
        cast(NO_SH2_POR as varchar)               as no_sh2_pt
    from {{ source('comex_aux', 'ncm_sh') }}
)

select
    ncm.co_ncm,
    ncm.no_ncm_pt,
    ncm.co_unid,
    ncm.co_sh6,
    sh.co_sh4,
    sh.co_sh2,
    sh.no_sh6_pt,
    sh.no_sh4_pt,
    sh.no_sh2_pt
from ncm
left join sh using (co_sh6)
