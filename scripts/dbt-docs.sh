#!/usr/bin/env bash
# =============================================================================
# Comex Brasil — scripts/dbt-docs.sh
#
# Gera e serve a documentação do dbt (lineage, colunas, testes).
#
# Uso:
#   ./scripts/dbt-docs.sh generate   # gera os arquivos em dbt/target/
#   ./scripts/dbt-docs.sh serve      # serve em http://localhost:8081
#
# Por que dois passos separados:
#   - `generate` roda dentro do container (precisa do dbt)
#   - `serve` roda no host (porque o scheduler não expõe porta pro host)
# =============================================================================

set -euo pipefail

CONTAINER="airflow-scheduler"
DBT_DIR="/opt/airflow/dbt"
COMMAND="${1:-generate}"

case "${COMMAND}" in

    generate)
        if ! docker compose ps --status running --services 2>/dev/null | grep -q "^${CONTAINER}$"; then
            echo "ERRO: container '${CONTAINER}' não está em execução."
            echo "Suba o ambiente primeiro: docker compose up -d"
            exit 1
        fi
        echo ">> Gerando documentação dbt..."
        docker compose exec -T "${CONTAINER}" \
            bash -c "cd ${DBT_DIR} && dbt --no-use-colors docs generate --profiles-dir ${DBT_DIR}"
        echo
        echo ">> Documentação gerada em dbt/target/"
        echo ">> Para visualizar: ./scripts/dbt-docs.sh serve"
        ;;

    serve)
        if [ ! -f "dbt/target/index.html" ]; then
            echo "ERRO: documentação não encontrada em dbt/target/"
            echo "Gere primeiro: ./scripts/dbt-docs.sh generate"
            exit 1
        fi
        echo ">> Servindo dbt docs em http://localhost:8081"
        echo ">> Pressione Ctrl+C para parar."
        echo
        cd dbt/target && python -m http.server 8081
        ;;

    *)
        echo "Uso: $0 [generate|serve]"
        exit 1
        ;;

esac
