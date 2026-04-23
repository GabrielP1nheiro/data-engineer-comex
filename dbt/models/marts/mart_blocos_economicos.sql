{{
  config(
    materialized='table'
  )
}}

-- =============================================================================
-- mart_blocos_economicos
--
-- Valor FOB por bloco econômico (Mercosul, União Europeia, Ásia, etc),
-- ano, mês e direção.
--
-- IMPORTANTE: um país pode pertencer a múltiplos blocos (ex: Alemanha em
-- UE e OCDE). Como stg_blocos tem 1 linha por (país, bloco), um JOIN
-- simples com core_comercio MULTIPLICARIA os valores de comércio de um
-- país que está em N blocos. Isso é INTENCIONAL: a pergunta "qual o
-- comércio Brasil-UE?" quer somar TUDO que foi com UE, mesmo que o país
-- também esteja na OCDE. Cada linha do mart responde a um bloco de cada
-- vez — não se soma o mart inteiro sem um filtro de bloco.
--
-- Responde:
--   3. "Como evoluiu a participação da China nas importações?" (via país)
--   6. "Quais blocos econômicos têm maior peso na pauta exportadora?"
--
-- Grão: (ano, mes, direcao, co_bloco)
-- =============================================================================

with comercio_com_blocos as (
    select
        c.ano,
        c.mes,
        c.data_ref,
        c.direcao,
        b.co_bloco,
        b.no_bloco,
        c.vl_fob_usd,
        c.kg_liquido
    from {{ ref('core_comercio') }} c
    inner join {{ ref('stg_blocos') }} b using (co_pais)
)

select
    ano,
    mes,
    data_ref,
    direcao,
    co_bloco,
    no_bloco,
    sum(vl_fob_usd)  as vl_fob_usd,
    sum(kg_liquido)  as kg_liquido
from comercio_com_blocos
group by 1, 2, 3, 4, 5, 6
