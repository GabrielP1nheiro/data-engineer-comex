"""
Builders de linha de comando para os ``BashOperator`` da DAG.

Manter as strings aqui (e não inline no arquivo da DAG) deixa o código
declarativo no topo e permite testar os comandos gerados sem subir o
Airflow. Tudo é montado com ``shlex.join`` para escapar corretamente
valores que venham de Variables ou ``dagrun.conf``.
"""

from __future__ import annotations

import json
import shlex

from .paths import DBT_DIR, INGESTION_DIR


DOWNLOAD_SCRIPT = INGESTION_DIR / "download.py"
CONVERT_SCRIPT = INGESTION_DIR / "convert_to_parquet.py"


def build_download_command(
    anos: list[int],
    direcao: str = "ambos",
    baixar_aux: bool = True,
    force: bool = True,
) -> str:
    """Comando que chama ``ingestion/download.py`` com os flags da DAG."""
    cmd: list[str] = [
        "python",
        str(DOWNLOAD_SCRIPT),
        "--anos",
        *[str(a) for a in anos],
        "--direcao",
        direcao,
    ]
    if not baixar_aux:
        cmd.append("--sem-aux")
    if force:
        cmd.append("--force")
    return shlex.join(cmd)


def build_convert_command(
    direcao: str = "ambos",
    converter_aux: bool = True,
    force: bool = True,
) -> str:
    """Comando que chama ``ingestion/convert_to_parquet.py``."""
    cmd: list[str] = [
        "python",
        str(CONVERT_SCRIPT),
        "--direcao",
        direcao,
    ]
    if not converter_aux:
        cmd.append("--sem-aux")
    if force:
        cmd.append("--force")
    return shlex.join(cmd)


def build_dbt_build_command(
    dbt_vars: dict[str, int],
    target: str = "duckdb",
    fail_fast: bool = True,
) -> str:
    """
    Comando para ``dbt build`` executado dentro do container.

    Precisa rodar com ``cwd=DBT_DIR`` porque o adaptador ``dbt-duckdb``
    resolve o ``path:`` do ``profiles.yml`` relativo ao diretório corrente,
    e não a ``--project-dir``. Sem o ``cd``, o caminho ``../data/comex.duckdb``
    vira ``/tmp/.../data/comex.duckdb`` quando disparado pelo BashOperator.
    Mesmo padrão usado por ``scripts/dbt.sh``.
    """
    vars_json = json.dumps(dbt_vars, separators=(",", ":"))
    dbt_cmd: list[str] = [
        "dbt",
        "--no-use-colors",
        "build",
        "--profiles-dir",
        str(DBT_DIR),
        "--target",
        target,
        "--vars",
        vars_json,
    ]
    if fail_fast:
        dbt_cmd.append("--fail-fast")
    return f"cd {shlex.quote(str(DBT_DIR))} && {shlex.join(dbt_cmd)}"
