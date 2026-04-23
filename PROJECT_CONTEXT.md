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
  - Tabelas auxiliares: NCM, países, UF, vias, URF

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

---

## Roadmap de versões

### v0.1 — Infraestrutura base
- [ ] Estrutura de pastas do projeto
- [ ] `docker-compose.yml` com Airflow
- [ ] Script de download dos CSVs do MDIC
- [ ] Conversão CSV → Parquet
- [ ] README inicial

### v0.2 — dbt local com DuckDB
- [ ] Configuração do dbt Core com adaptador DuckDB
- [ ] `profiles.yml` para DuckDB local
- [ ] Model `staging` (limpeza e tipagem dos dados brutos)
- [ ] Model `core` (regras de negócio, joins com tabelas auxiliares)
- [ ] Model `marts` (agregações analíticas prontas para consumo)
- [ ] Testes dbt (not_null, unique, relationships)
- [ ] `dbt docs generate` funcionando

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
│
├── data/
│   ├── raw/                         # CSVs originais do MDIC (gitignored)
│   ├── parquet/                     # Arquivos convertidos (gitignored)
│   └── aux/                         # Tabelas auxiliares (NCM, países, UF)
│
├── ingestion/
│   ├── download.py                  # Script de download dos CSVs do MDIC
│   ├── convert_to_parquet.py        # Conversão CSV → Parquet
│   └── requirements.txt
│
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml                 # Perfis: duckdb (local), bigquery (GCP), oci (OCI)
│   ├── models/
│   │   ├── staging/                 # Limpeza e tipagem
│   │   │   ├── stg_exportacoes.sql
│   │   │   ├── stg_importacoes.sql
│   │   │   └── stg_ncm.sql
│   │   ├── core/                    # Regras de negócio
│   │   │   ├── core_comercio.sql
│   │   │   └── core_produtos.sql
│   │   └── marts/                   # Agregações para consumo
│   │       ├── mart_balanca_comercial.sql
│   │       ├── mart_exportacoes_por_estado.sql
│   │       └── mart_top_produtos.sql
│   ├── tests/
│   └── macros/
│
├── airflow/
│   ├── dags/
│   │   ├── dag_ingestion.py         # Download + conversão Parquet
│   │   ├── dag_transformation.py    # Dispara dbt run
│   │   └── dag_pipeline.py          # Pipeline completo end-to-end
│   └── plugins/
│
├── dashboard/
│   └── streamlit_app.py             # App Streamlit (alternativa ao Metabase)
│
└── docs/
    ├── architecture.md              # Decisões arquiteturais detalhadas
    └── images/                      # Screenshots e diagramas
```

---

## Modelos dbt planejados

### Staging (limpeza e tipagem)
- `stg_exportacoes` — dados brutos de exportação com tipos corretos
- `stg_importacoes` — dados brutos de importação com tipos corretos
- `stg_ncm` — tabela auxiliar de produtos (Nomenclatura Comum do Mercosul)
- `stg_paises` — tabela auxiliar de países
- `stg_uf` — tabela auxiliar de estados brasileiros

### Core (regras de negócio)
- `core_comercio` — union de exportações e importações com flag de direção
- `core_produtos` — produtos enriquecidos com descrição NCM e categoria

### Marts (consumo analítico)
- `mart_balanca_comercial` — saldo por ano/mês/estado
- `mart_exportacoes_por_estado` — ranking de estados exportadores
- `mart_importacoes_por_estado` — ranking de estados importadores
- `mart_top_produtos` — principais produtos por valor FOB
- `mart_blocos_economicos` — agrupamento por bloco (Mercosul, UE, Ásia, etc.)

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

- **Dados grandes:** Os CSVs do MDIC podem ter vários GBs por ano — o `.gitignore` deve excluir a pasta `data/raw/` e `data/parquet/`
- **Custo cloud:** GCP tem 1TB/mês de queries no BigQuery gratuito — suficiente para o projeto. OCI tem free tier permanente mais generoso que o GCP
- **Migração dbt:** Apenas o `profiles.yml` muda entre DuckDB, BigQuery e OCI. Os models SQL permanecem idênticos
- **Airflow e memória:** O Airflow via Docker consome 2–4GB de RAM. Em máquinas com menos memória, considerar Prefect como alternativa mais leve
- **Snowflake:** Pode ser adicionado via trial de 30 dias em qualquer versão — basta adicionar um perfil no `profiles.yml`

---

## Como usar este arquivo com IA

Ao iniciar uma nova sessão, cole o conteúdo deste arquivo e diga:
> "Leia o PROJECT_CONTEXT.md abaixo e me ajude a continuar o desenvolvimento do projeto Comex Brasil."

O assistente terá todo o contexto necessário para continuar de onde parou.

---

*Última atualização: Abril 2026*
*Versão atual do projeto: v0.0 (planejamento)*
