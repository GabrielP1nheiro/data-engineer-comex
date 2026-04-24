#!/usr/bin/env bash
# =============================================================================
# Comex Brasil — scripts/seed_airflow_variables.sh
#
# Importa as Airflow Variables a partir de airflow/variables.json para dentro
# do metastore do Airflow (container airflow-scheduler).
#
# Rode uma vez após o `docker compose up -d` inicial, ou sempre que
# airflow/variables.json for alterado no repositório.
#
# Uso:
#   ./scripts/seed_airflow_variables.sh
#
# Variáveis importadas:
#   - comex_anos         (list)  janela de anos p/ download + convert
#   - comex_dbt_vars     (dict)  {ano_inicio, ano_fim} p/ dbt build --vars
#   - comex_dbt_target   (str)   target do profiles.yml (duckdb em v0.3)
# =============================================================================

set -euo pipefail

# Git Bash no Windows reescreve caminhos Linux (/tmp/...) para caminhos do
# Windows quando passados a `docker compose`. Esse export desativa isso.
export MSYS_NO_PATHCONV=1

CONTAINER="airflow-scheduler"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_FILE="${REPO_ROOT}/airflow/variables.json"
REMOTE_PATH="/tmp/comex_variables.json"

if ! docker compose ps --status running --services 2>/dev/null | grep -q "^${CONTAINER}$"; then
    echo "ERRO: o container '${CONTAINER}' não está em execução."
    echo "Suba o ambiente primeiro: docker compose up -d"
    exit 1
fi

if [[ ! -f "${LOCAL_FILE}" ]]; then
    echo "ERRO: arquivo de seed não encontrado: ${LOCAL_FILE}"
    exit 1
fi

echo "📋 Importando Airflow Variables de ${LOCAL_FILE}..."

# Evitamos `docker compose cp` porque o Git Bash no Windows converte mal o
# caminho de origem (/c/... vira C:\c:\...). Pipe via stdin é portável.
docker compose exec -T "${CONTAINER}" bash -c "cat > ${REMOTE_PATH}" < "${LOCAL_FILE}"
docker compose exec -T "${CONTAINER}" airflow variables import "${REMOTE_PATH}"
docker compose exec -T "${CONTAINER}" rm -f "${REMOTE_PATH}"

echo ""
echo "✅ Variables importadas. Valores atuais:"
docker compose exec -T "${CONTAINER}" airflow variables list
