import duckdb
con = duckdb.connect('/opt/airflow/data/comex.duckdb', read_only=True)

print('=== Top 5 produtos exportados em 2024 ===')
print(con.sql("""
    select co_ncm, no_ncm_pt, vl_fob_usd/1e9 as bilhoes_usd
    from main_marts.mart_top_produtos
    where ano = 2024 and direcao = 'EXP' and rank_ano_direcao <= 5
    order by rank_ano_direcao
""").df().to_string())

print()
print('=== Top 5 produtos importados em 2024 ===')
print(con.sql("""
    select co_ncm, no_ncm_pt, vl_fob_usd/1e9 as bilhoes_usd
    from main_marts.mart_top_produtos
    where ano = 2024 and direcao = 'IMP' and rank_ano_direcao <= 5
    order by rank_ano_direcao
""").df().to_string())

print()
print('=== Saldo comercial por ano ===')
print(con.sql("""
    select ano,
           sum(vl_exp_fob_usd)/1e9 as exp_bi,
           sum(vl_imp_fob_usd)/1e9 as imp_bi,
           sum(saldo_fob_usd)/1e9  as saldo_bi
    from main_marts.mart_balanca_comercial
    group by 1 order by 1
""").df().to_string())
