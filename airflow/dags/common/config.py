"""
Resolução de parâmetros da DAG.

Precedência (da maior para a menor):

1. ``dag_run.conf`` — override pontual ao disparar manualmente a DAG.
2. Airflow Variables — fonte padrão, editável pela UI sem redeploy.
3. Defaults no código (último recurso).

Essa camada existe para que a DAG não leia Variables diretamente — assim
os helpers ficam unit-testáveis sem precisar subir o Airflow.
"""

from __future__ import annotations

from typing import Any

from airflow.models import Variable


VAR_ANOS = "comex_anos"
VAR_DBT_VARS = "comex_dbt_vars"
VAR_DBT_TARGET = "comex_dbt_target"

DEFAULT_ANOS: list[int] = [2020, 2021, 2022, 2023, 2024]
DEFAULT_DBT_VARS: dict[str, int] = {"ano_inicio": 2020, "ano_fim": 2024}
DEFAULT_DBT_TARGET = "duckdb"


def _conf(dag_run_conf: dict[str, Any] | None) -> dict[str, Any]:
    return dag_run_conf or {}


def get_anos(dag_run_conf: dict[str, Any] | None = None) -> list[int]:
    """Janela de anos usada em ``download.py`` e ``convert_to_parquet.py``."""
    conf = _conf(dag_run_conf)
    if "anos" in conf:
        return [int(a) for a in conf["anos"]]
    return Variable.get(VAR_ANOS, default_var=DEFAULT_ANOS, deserialize_json=True)


def get_dbt_vars(dag_run_conf: dict[str, Any] | None = None) -> dict[str, int]:
    """Vars passadas ao ``dbt build`` via ``--vars`` (ano_inicio / ano_fim)."""
    conf = _conf(dag_run_conf)
    if "dbt_vars" in conf:
        return {k: int(v) for k, v in conf["dbt_vars"].items()}
    return Variable.get(
        VAR_DBT_VARS, default_var=DEFAULT_DBT_VARS, deserialize_json=True
    )


def get_dbt_target(dag_run_conf: dict[str, Any] | None = None) -> str:
    """
    Target do ``profiles.yml`` usado pela DAG.

    v0.3: ``duckdb`` (default). v1.1: ``bigquery`` via override.
    """
    conf = _conf(dag_run_conf)
    if "dbt_target" in conf:
        return str(conf["dbt_target"])
    return Variable.get(VAR_DBT_TARGET, default_var=DEFAULT_DBT_TARGET)


def get_force(dag_run_conf: dict[str, Any] | None = None) -> bool:
    """
    Se ``True``, ingestão re-baixa/reprocessa mesmo com arquivos existentes.

    Default na v0.3 é ``True`` para capturar atualizações intra-mês do MDIC
    (decisão #4 do PLAN_V0.3.md).
    """
    conf = _conf(dag_run_conf)
    if "force" in conf:
        return bool(conf["force"])
    return True
