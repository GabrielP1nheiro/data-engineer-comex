#!/usr/bin/env bash
# =============================================================================
# Comex Brasil — scripts/dbt.sh
#
# Wrapper para executar comandos dbt dentro do container airflow-scheduler.
# Usa o próprio profiles.yml do repositório (versionado) em vez do ~/.dbt/.
#
# Uso:
#   ./scripts/dbt.sh debug           # testa a conexão DuckDB
#   ./scripts/dbt.sh run             # roda todos os models
#   ./scripts/dbt.sh test            # roda todos os testes
#   ./scripts/dbt.sh build           # run + test (recomendado no dia-a-dia)
#   ./scripts/dbt.sh docs generate   # gera a documentação
#   ./scripts/dbt.sh run --select staging   # argumentos extras passam direto
# =============================================================================

set -euo pipefail

CONTAINER="airflow-scheduler"
DBT_DIR="/opt/airflow/dbt"

# Verifica se o container está em execução
if ! docker compose ps --status running --services 2>/dev/null | grep -q "^${CONTAINER}$"; then
    echo "ERRO: o container '${CONTAINER}' não está em execução."
    echo "Suba o ambiente primeiro: docker compose up -d"
    exit 1
fi

# Executa o comando dbt com profiles-dir apontando pro próprio projeto
docker compose exec -T "${CONTAINER}" \
    bash -c "cd ${DBT_DIR} && dbt --no-use-colors $* --profiles-dir ${DBT_DIR}"
