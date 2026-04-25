"""
Camada de acesso ao warehouse — sempre read-only.

Espelha o padrão de seam de ``airflow/dags/common/paths.py`` (v0.3): a variável
de ambiente ``COMEX_DB_TARGET`` decide o backend. Em v0.4 apenas ``duckdb``
está implementado; ``bigquery`` fica estubado para a v1.1.

Proteção contra escrita acidental:
- ``read_only=True`` na conexão DuckDB
- bind mount ``./data:/data:ro`` no docker-compose
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import streamlit as st


DB_TARGET = os.getenv("COMEX_DB_TARGET", "duckdb")
DUCKDB_PATH = os.getenv("COMEX_DUCKDB_PATH", "/data/comex.duckdb")
SCHEMA_MARTS = os.getenv("COMEX_SCHEMA_MARTS", "main_marts")
SCHEMA_CORE = os.getenv("COMEX_SCHEMA_CORE", "main_core")

_VALID_TARGETS = ("duckdb", "bigquery")


def warehouse_exists() -> bool:
    """True se o warehouse está disponível (DuckDB → arquivo no disco)."""
    if DB_TARGET == "duckdb":
        return Path(DUCKDB_PATH).exists()
    return True


@st.cache_resource
def get_connection():
    """Conexão singleton, sempre em modo somente leitura.

    Cacheada no servidor — uma conexão por processo Streamlit.
    """
    if DB_TARGET == "duckdb":
        return duckdb.connect(DUCKDB_PATH, read_only=True)
    if DB_TARGET == "bigquery":
        raise NotImplementedError(
            "Target 'bigquery' será implementado na v1.1 (migração GCP)."
        )
    raise ValueError(
        f"COMEX_DB_TARGET inválido: {DB_TARGET!r}. Aceitos: {_VALID_TARGETS}."
    )


def warehouse_mtime() -> str | None:
    """Timestamp ISO do mtime do warehouse local; ``None`` se não aplicável."""
    if DB_TARGET != "duckdb":
        return None
    path = Path(DUCKDB_PATH)
    if not path.exists():
        return None
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.astimezone().isoformat(timespec="seconds")
