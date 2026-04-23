{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- core_produtos
--
-- Dimensão de produtos NCM. A camada staging já faz o join com NCM_SH
-- (hierarquia), então aqui apenas enriquecemos com a descrição textual
-- da unidade estatística quando disponível.
--
-- Em versões futuras este model pode incluir:
--   - Classificação por intensidade tecnológica
--   - Agrupamento por setor (agropecuária, indústria, etc)
--   - Fator agregado (básico, semi-manufaturado, manufaturado)
--
-- Grão: 1 linha por NCM de 8 dígitos.
-- =============================================================================

select
    co_ncm,
    no_ncm_pt,
    co_unid,
    co_sh2,
    no_sh2_pt,
    co_sh4,
    no_sh4_pt,
    co_sh6,
    no_sh6_pt
from {{ ref('stg_ncm') }}
