"""
Caminhos dentro do container do Airflow e abstração de sink.

Centraliza as constantes de path para evitar drift de string literal entre
tasks da DAG e para criar a *seam* que, na v1.1 (GCP/BigQuery), permite
trocar o destino dos Parquet de disco local para GCS sem mexer na DAG.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath


# Sempre POSIX: esses caminhos existem dentro do container Linux do Airflow,
# independentemente do SO onde os testes rodam.
INGESTION_DIR = PurePosixPath("/opt/airflow/ingestion")
DBT_DIR = PurePosixPath("/opt/airflow/dbt")
DATA_DIR = PurePosixPath("/opt/airflow/data")
PARQUET_DIR = DATA_DIR / "parquet"


_VALID_SINKS = ("local", "gcs")

SINK = os.getenv("COMEX_SINK", "local")


def get_parquet_sink() -> str:
    """
    Retorna onde os arquivos Parquet devem ser escritos/lidos.

    v0.3: ``local`` — devolve o caminho dentro do container.
    v1.1: ``gcs``   — devolverá uma URI ``gs://...`` (ainda não implementado).
    """
    if SINK == "local":
        return str(PARQUET_DIR)
    if SINK == "gcs":
        # Seam declarado; a implementação real entra na v1.1 (issue futura).
        raise NotImplementedError(
            "Sink 'gcs' será implementado na v1.1 (migração para BigQuery)."
        )
    raise ValueError(
        f"COMEX_SINK inválido: {SINK!r}. Valores aceitos: {_VALID_SINKS}."
    )
