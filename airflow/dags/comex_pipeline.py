"""
Comex Brasil — DAG principal (v0.3)
===================================

Pipeline mensal que baixa os CSVs do MDIC, converte para Parquet e roda
o ``dbt build`` sobre o DuckDB local. É o equivalente orquestrado do
fluxo manual da v0.2.

Topologia
---------

::

    start  ─▶  resolve_commands  ─▶  ingest{download ▶ convert}
                                  ─▶  transform{dbt_build}
                                  ─▶  end

Idempotência
------------

* ``download.py`` e ``convert_to_parquet.py`` são idempotentes por default.
* ``dbt build`` materializa ``view``/``table`` em full-refresh (~25 s).
* ``--force`` é ``True`` por padrão (decisão #4 do PLAN_V0.3.md) para
  capturar atualizações intra-mês do CSV do ano corrente no MDIC.

Override por execução
---------------------

Parâmetros aceitos em ``dag_run.conf`` ao disparar manualmente:

* ``anos``: ``list[int]`` — janela de anos (ex.: ``[2024]`` p/ backfill).
* ``dbt_vars``: ``{"ano_inicio": int, "ano_fim": int}``.
* ``dbt_target``: ``str`` — target do ``profiles.yml``.
* ``force``: ``bool`` — desliga ``--force`` se ``False``.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.task_group import TaskGroup

from common.bash_commands import (
    build_convert_command,
    build_dbt_build_command,
    build_download_command,
)
from common.config import get_anos, get_dbt_target, get_dbt_vars, get_force


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
}


@dag(
    dag_id="comex_pipeline",
    description="MDIC CSV → Parquet → DuckDB (dbt build). Refresh mensal.",
    schedule="0 6 25 * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    dagrun_timeout=timedelta(hours=2),
    tags=["comex", "v0.3", "monthly"],
    doc_md=__doc__,
)
def comex_pipeline():
    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    @task
    def resolve_commands(**context) -> dict[str, str]:
        """
        Resolve parâmetros (``dag_run.conf`` > Airflow Variable > default)
        e monta os três comandos shell consumidos pelos BashOperators.

        Centralizar aqui mantém a lógica de config unit-testável e evita
        lookups repetidos às Variables dentro dos templates Jinja.
        """
        dag_run = context.get("dag_run")
        conf = dag_run.conf if dag_run else None

        anos = get_anos(conf)
        dbt_vars = get_dbt_vars(conf)
        target = get_dbt_target(conf)
        force = get_force(conf)

        return {
            "download": build_download_command(anos=anos, force=force),
            "convert": build_convert_command(force=force),
            "dbt_build": build_dbt_build_command(dbt_vars=dbt_vars, target=target),
        }

    cmds = resolve_commands()

    with TaskGroup(group_id="ingest") as ingest:
        download = BashOperator(
            task_id="download",
            bash_command="{{ ti.xcom_pull(task_ids='resolve_commands')['download'] }}",
            retries=3,
            retry_delay=timedelta(minutes=5),
            retry_exponential_backoff=True,
            execution_timeout=timedelta(minutes=90),
        )
        convert = BashOperator(
            task_id="convert",
            bash_command="{{ ti.xcom_pull(task_ids='resolve_commands')['convert'] }}",
            retries=1,
            retry_delay=timedelta(minutes=2),
            execution_timeout=timedelta(minutes=30),
        )
        download >> convert

    with TaskGroup(group_id="transform") as transform:
        BashOperator(
            task_id="dbt_build",
            bash_command="{{ ti.xcom_pull(task_ids='resolve_commands')['dbt_build'] }}",
            retries=0,
            execution_timeout=timedelta(minutes=15),
        )

    start >> cmds >> ingest >> transform >> end


comex_pipeline()
