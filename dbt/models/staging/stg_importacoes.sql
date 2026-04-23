{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_importacoes
--
-- Mesma estrutura de stg_exportacoes + VL_FRETE / VL_SEGURO / VL_CIF calculado.
-- Importações seguem o padrão CIF = FOB + frete + seguro (referência BACEN).
-- =============================================================================

with fonte as (
    select * from {{ source('comex_raw', 'importacoes') }}
    where cast(CO_ANO as integer) between {{ var('ano_inicio') }} and {{ var('ano_fim') }}
)

select
    cast(CO_ANO as integer)                                as ano,
    lpad(cast(CO_MES  as varchar), 2, '0')                 as mes,
    make_date(cast(CO_ANO as integer), cast(CO_MES as integer), 1) as data_ref,
    lpad(cast(CO_NCM  as varchar), 8, '0')                 as co_ncm,
    cast(CO_UNID as varchar)                               as co_unid,
    lpad(cast(CO_PAIS as varchar), 3, '0')                 as co_pais,
    cast(SG_UF_NCM as varchar)                             as sg_uf,
    cast(CO_VIA as varchar)                                as co_via,
    lpad(cast(CO_URF  as varchar), 7, '0')                 as co_urf,
    cast(QT_ESTAT as bigint)                               as qt_estat,
    cast(KG_LIQUIDO as bigint)                             as kg_liquido,
    cast(VL_FOB as double)                                 as vl_fob_usd,
    cast(VL_FRETE  as double)                              as vl_frete_usd,
    cast(VL_SEGURO as double)                              as vl_seguro_usd,
    -- CIF = FOB + frete + seguro
    cast(VL_FOB as double)
        + coalesce(cast(VL_FRETE  as double), 0)
        + coalesce(cast(VL_SEGURO as double), 0)           as vl_cif_usd
from fonte
