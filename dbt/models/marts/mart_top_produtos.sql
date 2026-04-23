{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- mart_top_produtos
--
-- Valor FOB por produto (NCM) e direção, com enriquecimento de descrição e
-- hierarquia SH vinda de core_produtos. Útil para ranking dos "top N
-- produtos exportados/importados" por ano.
--
-- Responde:
--   2. "Quais são os 10 principais produtos exportados por valor FOB?"
--
-- Grão: (ano, direcao, co_ncm)
-- =============================================================================

with por_produto as (
    select
        ano,
        direcao,
        co_ncm,
        sum(vl_fob_usd)  as vl_fob_usd,
        sum(kg_liquido)  as kg_liquido
    from {{ ref('core_comercio') }}
    group by 1, 2, 3
)

select
    p.ano,
    p.direcao,
    p.co_ncm,
    prod.no_ncm_pt,
    prod.co_sh2,
    prod.no_sh2_pt,
    prod.co_sh4,
    prod.no_sh4_pt,
    p.vl_fob_usd,
    p.kg_liquido,
    -- Participação do NCM no total do ano, dentro da mesma direção
    p.vl_fob_usd
        / nullif(sum(p.vl_fob_usd) over (partition by p.ano, p.direcao), 0)
        as share_direcao_ano,
    -- Ranking dentro do ano + direção (1 = maior)
    rank() over (
        partition by p.ano, p.direcao
        order by p.vl_fob_usd desc
    ) as rank_ano_direcao
from por_produto p
left join {{ ref('core_produtos') }} prod using (co_ncm)
