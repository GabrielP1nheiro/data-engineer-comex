{{
  config(
    materialized='view'
  )
}}

-- =============================================================================
-- stg_exportacoes
--
-- Exportações tipadas e filtradas pela janela de anos (ano_inicio / ano_fim).
--
-- IMPORTANTE: as colunas CO_* vêm como BIGINT no Parquet (o conversor não
-- preservou zeros à esquerda). Para que os joins com as auxiliares funcionem,
-- casamos aqui para VARCHAR com LPAD nos padrões oficiais do MDIC:
--   CO_MES -> 2 dígitos   (01..12)
--   CO_NCM -> 8 dígitos
--   CO_PAIS -> 3 dígitos
--   CO_URF -> 7 dígitos
-- =============================================================================

with fonte as (
    select * from {{ source('comex_raw', 'exportacoes') }}
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
    cast(VL_FOB as double)                                 as vl_fob_usd
from fonte
