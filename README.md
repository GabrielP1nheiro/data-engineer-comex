# Comex Brasil — Data Engineering Portfolio

> Pipeline de Data Engineering end-to-end usando dados públicos de comércio exterior brasileiro (MDIC / Comex Stat).

## Status do projeto
![Version](https://img.shields.io/badge/version-v0.1-blue)
![Status](https://img.shields.io/badge/status-infraestrutura%20base-brightgreen)

## Sobre o projeto

Este projeto constrói um pipeline completo de Data Engineering sobre dados públicos de exportação e importação brasileira, disponibilizados pelo Ministério do Desenvolvimento, Indústria e Comércio (MDIC) via Comex Stat.

O objetivo é demonstrar habilidades práticas de engenharia de dados — desde a ingestão de arquivos brutos até dashboards analíticos — evoluindo de um ambiente local para cloud (GCP e OCI).

## Perguntas de negócio respondidas

- Qual a balança comercial do Brasil por estado nos últimos 5 anos?
- Quais são os 10 principais produtos exportados por valor FOB?
- Como evoluiu a participação da China nas importações brasileiras?
- Como a pandemia (2020) impactou o comércio exterior brasileiro?
- Quais blocos econômicos têm maior peso na pauta exportadora?

## Arquitetura

```
MDIC / Comex Stat (CSV)
        │
        ▼
  Python + Polars (download + conversão Parquet)
        │
        ▼
  DuckDB ◄── dbt Core (staging → core → marts)
        │
        ▼
  Apache Airflow (orquestração)
        │
        ▼
  Streamlit / Metabase (dashboards)

  Fase 2: DuckDB → BigQuery (GCP)
  Fase 3: BigQuery → OCI Autonomous DB
```

## Stack

| Camada | Ferramenta |
|---|---|
| Containerização | Docker + Docker Compose |
| Ingestão | Python + Polars |
| Engine analítica local | DuckDB |
| Transformação | dbt Core |
| Orquestração | Apache Airflow |
| Visualização | Streamlit |
| Cloud (fase 2) | GCP — BigQuery + Cloud Storage |
| Cloud (fase 3) | OCI — Object Storage + Autonomous DB |

## Volume de dados (5 anos: 2020–2024)

| Direção | Linhas | CSV | Parquet | Compressão |
|---|---|---|---|---|
| Exportação (EXP) | 7.488.174 | 475 MB | 77 MB | 6.2x |
| Importação (IMP) | 10.169.636 | 711 MB | 132 MB | 5.4x |
| Tabelas auxiliares | 21.298 | 11 MB | 1.3 MB | 8.5x |
| **Total** | **~17.7 milhões** | **~1.2 GB** | **~210 MB** | **5.7x** |

## Roadmap

- [x] **v0.1 — Infraestrutura base (Docker + ingestão)**
- [ ] v0.2 — dbt local com DuckDB
- [ ] v0.3 — Orquestração com Airflow
- [ ] v0.4 — Visualização (Streamlit)
- [ ] v1.0 — MVP completo local
- [ ] v1.1 — Migração para GCP (BigQuery)
- [ ] v1.2 — Camada OCI
- [ ] v2.0 — Camada de IA (agentes sobre os dados)

## Fonte de dados

Dados públicos disponíveis em: https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta

**Padrão de URL dos arquivos:**
- Exportação: `https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/EXP_{ANO}.csv`
- Importação: `https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/IMP_{ANO}.csv`
- Tabelas auxiliares: `https://balanca.economia.gov.br/balanca/bd/tabelas/{NOME}.csv`

---

## Como executar

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução
- ~2 GB de espaço em disco para os dados (CSV + Parquet)
- ~4 GB de RAM livres (o Airflow consome 2–4 GB)

### 1. Subir o ambiente

```bash
# Primeira vez: faz o build da imagem customizada e sobe tudo
docker compose up -d --build

# Próximas vezes
docker compose up -d
```

Acesse o Airflow em http://localhost:8080 (usuário `admin` / senha `admin`).

### 2. Ingestão dos dados

**Baixar todos os CSVs do MDIC (EXP + IMP de 2020–2024 + tabelas auxiliares):**

```bash
docker compose exec airflow-scheduler python /opt/airflow/ingestion/download.py
```

**Converter os CSVs para Parquet (recomendado — economiza ~5x de espaço):**

```bash
docker compose exec airflow-scheduler python /opt/airflow/ingestion/convert_to_parquet.py
```

### 3. Opções disponíveis

```bash
# Download parcial: apenas anos específicos
python ingestion/download.py --anos 2023 2024

# Download apenas de exportações (sem importações)
python ingestion/download.py --direcao exp

# Sem tabelas auxiliares
python ingestion/download.py --sem-aux

# Forçar re-download (sobrescreve o que já existe)
python ingestion/download.py --force
```

Os mesmos argumentos (`--direcao`, `--sem-aux`, `--force`) também funcionam no `convert_to_parquet.py`.

### 4. Parar o ambiente

```bash
docker compose down          # preserva os dados
docker compose down -v       # apaga volumes (reset completo)
```

---

## Decisões técnicas e armadilhas conhecidas

### Encoding Latin-1 nos arquivos do MDIC

Os CSVs do MDIC vêm em **Latin-1 (ISO-8859-1)**, não UTF-8. Se lidos como UTF-8, acentos e caracteres especiais viram lixo (`Rond�nia` em vez de `Rondônia`). O script de conversão trata isso explicitamente.

### Códigos com zeros à esquerda

Campos como `CO_MES` (`"04"`), `CO_VIA` (`"04"`), `CO_URF` (`"0817600"`) precisam ser tratados como **string**, não integer — caso contrário os zeros à esquerda desaparecem e os joins com as tabelas auxiliares quebram. O schema Parquet preserva isso.

### Certificado SSL do gov.br no container

O servidor `balanca.economia.gov.br` usa certificado emitido pela ICP-Brasil, que não está na lista de CAs confiáveis da imagem Docker do Airflow. Como os dados são públicos e o host é um domínio `.gov.br`, o script de download desabilita a verificação SSL via `verify=False`. Essa decisão será revisitada na migração para cloud (v1.1+).

### Permissões de arquivo no Windows

Arquivos criados pelo container (usuário `airflow`, UID 50000) aparecem como "sem permissão" no Explorer do Windows. Clicar em "Continuar" ajusta as permissões uma vez e o aviso não retorna. Não afeta a leitura dos arquivos pelos scripts dentro do Docker.

---

## Estrutura do projeto

```
comex-brasil-de/
│
├── README.md                        # Este arquivo
├── PROJECT_CONTEXT.md               # Contexto completo (stack, roadmap, decisões)
├── .gitignore
├── docker-compose.yml               # Airflow + Postgres
├── Dockerfile.airflow               # Imagem customizada com dependências do projeto
│
├── data/
│   ├── raw/                         # CSVs originais do MDIC (gitignored)
│   │   ├── exp/
│   │   └── imp/
│   ├── parquet/                     # Arquivos convertidos (gitignored)
│   │   ├── exp/
│   │   └── imp/
│   └── aux/                         # Tabelas auxiliares (NCM, países, UF, etc)
│
├── ingestion/
│   ├── download.py                  # Download dos CSVs do MDIC
│   ├── convert_to_parquet.py        # Conversão CSV → Parquet
│   └── requirements.txt
│
├── dbt/                             # Models dbt (v0.2)
│   └── models/{staging,core,marts}/
│
├── airflow/                         # DAGs do Airflow (v0.3)
│   └── dags/
│
├── dashboard/                       # Streamlit (v0.4)
│
└── docs/
    └── images/
```

---

*Projeto em desenvolvimento — commits incrementais a cada versão*