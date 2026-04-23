{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- core_comercio
--
-- Fato unificado de comércio exterior: uma linha por transação (ano, mês,
-- NCM, país, UF, via, URF) com direção ('EXP' ou 'IMP').
--
-- Decisões de design:
--   - VL_FOB_USD existe em exp e imp -> coluna canônica.
--   - VL_FRETE / VL_SEGURO / VL_CIF só existem em imp -> NULL em exp.
--   - NÃO criamos um vl_usd "único": os marts escolhem FOB ou CIF conforme
--     a análise (balança comercial usa FOB de ambos; custo logístico usa CIF).
--
-- Grão: (ano, mes, co_ncm, co_pais, sg_uf, co_via, co_urf, direcao).
-- Observação: não há garantia de unicidade por esse grão nos dados brutos
-- do MDIC — podem existir múltiplas linhas com mesma chave natural para
-- uma mesma unidade estatística diferente. Mantemos fiel ao Parquet.
-- =============================================================================

with exportacoes as (
    select
        ano,
        mes,
        data_ref,
        'EXP'            as direcao,
        co_ncm,
        co_unid,
        co_pais,
        sg_uf,
        co_via,
        co_urf,
        qt_estat,
        kg_liquido,
        vl_fob_usd,
        cast(null as double)  as vl_frete_usd,
        cast(null as double)  as vl_seguro_usd,
        cast(null as double)  as vl_cif_usd
    from {{ ref('stg_exportacoes') }}
),

importacoes as (
    select
        ano,
        mes,
        data_ref,
        'IMP'            as direcao,
        co_ncm,
        co_unid,
        co_pais,
        sg_uf,
        co_via,
        co_urf,
        qt_estat,
        kg_liquido,
        vl_fob_usd,
        vl_frete_usd,
        vl_seguro_usd,
        vl_cif_usd
    from {{ ref('stg_importacoes') }}
)

select * from exportacoes
union all
select * from importacoes
