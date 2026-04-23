# Projeto Comex Brasil — Data Engineering Portfolio

## Contexto do desenvolvedor

- **Perfil atual:** Analista de BI em transição para Data Engineer
- **Objetivo:** Construir um projeto de portfólio robusto que demonstre habilidades de Data Engineering
- **Nível Python / CLI:** Intermediário
- **Experiência cloud:** Básico (já criou contas, explorou superficialmente GCP e OCI)
- **Cursos em andamento:** Semana AI Data Engineer 2026 (owshq-mec) — foco em agentes de IA, LlamaIndex, LangChain, CrewAI, MCP, Qdrant
- **Empresa atual:** Valoriza conhecimentos em GCP e OCI

---

## Objetivo do projeto

Construir um pipeline de Data Engineering end-to-end usando dados públicos de comércio exterior brasileiro (MDIC / Comex Stat), evoluindo de um ambiente local para cloud, documentado via GitHub com commits incrementais.

**Questão central respondida pelo projeto:**
> Como evoluir dados brutos de exportação/importação brasileira em insights confiáveis, rastreáveis e automatizados?

---

## Fonte de dados

- **Nome:** MDIC / Comex Stat
- **URL:** https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta
- **Formato:** Arquivos CSV públicos, atualizados mensalmente
- **Histórico disponível:** Desde 1989
- **Granularidade:** Por NCM (produto), país de destino/origem, estado brasileiro, modal de transporte, mês/ano
- **Tabelas principais:**
  - Exportações (EXP) — por ano
  - Importações (IMP) — por ano
  - Tabelas auxiliares: NCM, NCM_SH, países, UF, vias, URF

---

## Decisões arquiteturais

### Abordagem de desenvolvimento
- Desenvolvimento incremental via GitHub (commits frequentes, releases por versão)
- README escrito antes do código — descreve o projeto como se já estivesse pronto
- Cada versão (v0.1, v0.2...) é funcional e demonstrável de forma independente

### Stack técnica

| Camada | Ferramenta | Justificativa |
|---|---|---|
| Containerização | Docker + Docker Compose | Reprodutibilidade, sem dependências locais |
| Armazenamento local | Arquivos Parquet/CSV | DuckDB lê diretamente, sem banco intermediário |
| Engine analítica local | DuckDB | Gratuito, permanente, rápido em arquivos, portável |
| Transformação | dbt Core | Open source, suporta DuckDB e BigQuery nativamente |
| Orquestração | Apache Airflow | DAGs, padrão de mercado, roda via Docker |
| Visualização | Metabase ou Streamlit | Gratuito, conecta direto no DuckDB/BigQuery |
| Portfólio | GitHub + dbt docs | Lineage, testes, documentação automática |

### Decisão chave: DuckDB como engine local
- dbt roda as transformações diretamente sobre arquivos Parquet via DuckDB
- Não é necessário carregar dados em banco antes das transformações
- Migração para BigQuery (GCP) é feita apenas trocando o adaptador no `profiles.yml` do dbt
- Todo o código SQL dos models dbt permanece **inalterado** na migração

### Decisões da v0.2
- **Sources via `meta.external_location`** (sintaxe dbt-duckdb) apontando para globs de Parquet
- **Caminhos absolutos** no sources.yml (`/opt/airflow/data/...`) para evitar bugs de working directory
- **LPAD explícito** na staging para preservar zeros à esquerda perdidos na conversão CSV→Parquet (NCM 8 dígitos, PAIS 3, URF 7)
- **Materialização por camada**: staging=view, core=table, marts=table
- **Valor monetário único não foi criado em core_comercio** — FOB, frete, seguro e CIF ficam em colunas separadas; o mart escolhe qual usar

---

## Roadmap de versões

### v0.1 — Infraestrutura base ✅
- [x] Estrutura de pastas do projeto
- [x] `docker-compose.yml` com Airflow
- [x] Script de download dos CSVs do MDIC
- [x] Conversão CSV → Parquet
- [x] README inicial

### v0.2 — dbt local com DuckDB ✅
- [x] Configuração do dbt Core com adaptador DuckDB
- [x] `profiles.yml` para DuckDB local (+ placeholder BigQuery)
- [x] Models staging (8 views)
- [x] Models core (2 tables)
- [x] Models marts (5 tables)
- [x] 60 testes dbt (not_null, unique, relationships, accepted_values)
- [x] `dbt docs generate` funcionando
- [x] Script helper `./scripts/dbt.sh`
- [x] Volume `./dbt:/opt/airflow/dbt` no docker-compose

### v0.3 — Orquestração com Airflow
- [ ] DAG de ingestão (download + conversão Parquet)
- [ ] DAG de transformação (dispara dbt run)
- [ ] DAG completo end-to-end com dependências
- [ ] Agendamento mensal (alinhado com ciclo do MDIC)

### v0.4 — Visualização
- [ ] Metabase ou Streamlit conectado nos marts
- [ ] Dashboard: balança comercial por estado
- [ ] Dashboard: principais produtos exportados/importados
- [ ] Dashboard: evolução por bloco econômico (Mercosul, UE, Ásia)
- [ ] Screenshots para o README

### v1.0 — MVP completo local
- [ ] README detalhado com arquitetura, decisões e instruções
- [ ] dbt docs publicado (GitHub Pages ou similar)
- [ ] Diagrama de arquitetura no README
- [ ] Projeto público no GitHub

### v1.1 — Migração para GCP
- [ ] Conta GCP configurada (free tier)
- [ ] Bucket no Cloud Storage para os arquivos Parquet
- [ ] Dataset no BigQuery
- [ ] `profiles.yml` com perfil BigQuery
- [ ] `dbt run` funcionando no BigQuery sem alterar models
- [ ] Cloud Scheduler ou Cloud Composer para orquestração
- [ ] README atualizado com seção GCP

### v1.2 — Camada OCI
- [ ] Conta OCI configurada (free tier permanente)
- [ ] Object Storage como destino alternativo
- [ ] Autonomous Database ou ADW como engine analítica
- [ ] Demonstração de portabilidade no README
- [ ] README atualizado com seção OCI

### v2.0 — Camada de IA (futuro — pós curso AI Data Engineer)
- [ ] Agente que responde perguntas sobre os dados de comércio exterior
- [ ] RAG sobre relatórios e notas técnicas do MDIC
- [ ] Integração com stack do curso (LlamaIndex, LangChain, Qdrant)
- [ ] Interface via Chainlit

---

## Estrutura de pastas do projeto

```
comex-brasil-de/
│
├── README.md                        # Documentação principal do projeto
├── PROJECT_CONTEXT.md               # Este arquivo — contexto para o assistente de IA
├── .gitignore
├── docker-compose.yml               # Airflow + dependências
├── Dockerfile.airflow               # Imagem customizada
│
├── data/
│   ├── raw/                         # CSVs originais do MDIC (gitignored)
│   ├── parquet/                     # Arquivos convertidos (gitignored)
│   │   ├── exp/
│   │   ├── imp/
│   │   └── aux/
│   └── comex.duckdb                 # Data warehouse local (gitignored)
│
├── ingestion/
│   ├── download.py
│   ├── convert_to_parquet.py
│   └── requirements.txt
│
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml                 # Perfis: duckdb (local), bigquery (GCP)
│   ├── models/
│   │   ├── staging/                 # 8 views (stg_*)
│   │   ├── core/                    # 2 tables (core_*)
│   │   └── marts/                   # 5 tables (mart_*)
│   ├── tests/
│   ├── macros/
│   └── target/                      # dbt docs + manifest (gitignored)
│
├── scripts/
│   ├── dbt.sh                       # Wrapper para dbt dentro do container
│   └── dbt-docs.sh                  # Gera e serve a documentação dbt
│
├── airflow/
│   ├── dags/                        # DAGs (v0.3)
│   └── plugins/
│
├── dashboard/
│   └── streamlit_app.py             # App Streamlit (v0.4)
│
└── docs/
    ├── architecture.md
    └── images/
```

---

## Modelos dbt implementados (v0.2)

### Staging — views (limpeza e tipagem)
- `stg_exportacoes` — 7.5M linhas, EXP com LPAD aplicado nos códigos
- `stg_importacoes` — 10.2M linhas, IMP com cálculo de CIF = FOB + frete + seguro
- `stg_ncm` — NCM enriquecido com hierarquia SH2/SH4/SH6 (JOIN com NCM_SH)
- `stg_paises` — códigos MDIC + ISO3 numérico e alfabético
- `stg_uf` — UFs brasileiras + região
- `stg_vias` — vias de transporte
- `stg_urf` — Unidades da Receita Federal
- `stg_blocos` — relação país x bloco econômico

### Core — tables (regras de negócio)
- `core_comercio` — fato unificado exp+imp com flag `direcao`, ~17.7M linhas
- `core_produtos` — dimensão NCM com descrição PT e hierarquia SH completa

### Marts — tables (consumo analítico)
- `mart_balanca_comercial` — saldo FOB por ano/mês/UF
- `mart_exportacoes_por_estado` — ranking de UFs com share nacional
- `mart_importacoes_por_estado` — idem para IMP (FOB e CIF)
- `mart_top_produtos` — ranking de NCMs com hierarquia SH
- `mart_blocos_economicos` — comércio por bloco (MERCOSUL, UE, Ásia, etc)

---

## Perguntas de negócio que o projeto responde

1. Qual a balança comercial do Brasil por estado nos últimos 5 anos?
2. Quais são os 10 principais produtos exportados por valor FOB?
3. Como evoluiu a participação da China nas importações brasileiras?
4. Quais estados têm maior dependência de importações de insumos?
5. Como a pandemia (2020) impactou o comércio exterior brasileiro?
6. Quais blocos econômicos têm maior peso na pauta exportadora?

---

## Notas importantes

- **Dados grandes:** Os CSVs do MDIC podem ter vários GBs por ano — o `.gitignore` exclui `data/raw/`, `data/parquet/` e o `comex.duckdb`
- **Custo cloud:** GCP tem 1TB/mês de queries no BigQuery gratuito. OCI tem free tier permanente mais generoso que o GCP
- **Migração dbt:** Apenas o `profiles.yml` muda entre DuckDB, BigQuery e OCI. Os models SQL permanecem idênticos
- **Airflow e memória:** O Airflow via Docker consome 2–4GB de RAM
- **Snowflake:** Pode ser adicionado via trial de 30 dias em qualquer versão — basta adicionar um perfil no `profiles.yml`
- **Git Bash no Windows:** Exige `export MSYS_NO_PATHCONV=1` para não converter paths Unix em Windows ao chamar `docker exec`

---

## Como usar este arquivo com IA

Ao iniciar uma nova sessão, cole o conteúdo deste arquivo e diga:
> "Leia o PROJECT_CONTEXT.md abaixo e me ajude a continuar o desenvolvimento do projeto Comex Brasil."

O assistente terá todo o contexto necessário para continuar de onde parou.

---

*Última atualização: Abril 2026*
*Versão atual do projeto: v0.2*
