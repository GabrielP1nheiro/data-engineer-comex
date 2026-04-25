# PLAN v0.4 — Visualização (Streamlit + DuckDB)

> **Confidence:** 0.90 (HIGH) — KB: dbt marts já estabilizados (60 testes verdes em v0.2); Streamlit + DuckDB read-only é padrão documentado; sem dependências externas novas além de Streamlit + Plotly.
> **Scope:** Construir 3 dashboards (balança comercial, top produtos, blocos econômicos) lendo `main_marts.*` de `data/comex.duckdb` em modo read-only, dentro de container Docker.
> **Out of scope:** Autenticação, deploy público (GitHub Pages / Streamlit Cloud), métricas avançadas (forecasting, anomaly detection), migração para BigQuery (v1.1).

---

## 1. Stack & topologia

### Recommendation: **Streamlit multipage** servindo via container dedicado

Stack final:

| Camada | Escolha | Justificativa |
|---|---|---|
| Framework UI | **Streamlit 1.39.x** | Python puro, multipage nativo, alinhado com objetivo "tudo em Python" do projeto; código versionado (vs Metabase, que é GUI-driven) |
| Engine de leitura | **DuckDB 1.0.0 read_only=True** | Já é o warehouse local; abrir `read_only=True` permite leitura concorrente enquanto a DAG escreve em modo write — mitiga **Risco #2 do PLAN_V0.3.md** (file lock contention) |
| Charts | **Plotly 5.x** | Padrão de mercado, interativo, melhor material de portfólio que `st.line_chart` nativo; integra com Streamlit via `st.plotly_chart` |
| DataFrame | **Pandas 2.x** | DuckDB→pandas é zero-copy (Arrow); Streamlit serializa pandas nativamente |
| Container | **Imagem Python slim própria** (`Dockerfile.streamlit`) | Imagem do Airflow é 2GB+; isolar Streamlit em ~300MB facilita restart e migração futura |

Rejected alternatives:

| Opção | Por que rejeitada |
|---|---|
| Metabase (Docker) | UI bonita mas zero código no portfólio; conector DuckDB ainda experimental; perde controle sobre layout |
| Streamlit dentro do `airflow-scheduler` | Contamina imagem do Airflow; restart de um derruba o outro; deps Streamlit puxam protobuf que conflita com Airflow 2.9.3 |
| Altair/Vega-Lite | Bonito e dataframe-native, mas Plotly tem mais material e é mais comum em portfólios DE |
| Single page com `st.tabs` | Não escala; padrão multipage com `pages/` mostra conhecimento idiomático de Streamlit |
| Dash (Plotly) | Mais código boilerplate; público-alvo do portfólio espera Streamlit |

### Topologia de serviços

```
┌─────────────────────────────────────────────────────────────┐
│                    docker-compose.yml                       │
│                                                             │
│  ┌──────────────────┐         ┌────────────────────────┐    │
│  │ airflow-*        │  WRITE  │ ./data/comex.duckdb    │    │
│  │ (LocalExecutor)  │ ──────► │  (host bind mount)     │    │
│  └──────────────────┘         │                        │    │
│                               │                        │    │
│  ┌──────────────────┐  READ   │                        │    │
│  │ streamlit        │ ◄────── │                        │    │
│  │ :8501            │         └────────────────────────┘    │
│  └──────────────────┘                                       │
│       (read_only=True garante leitura segura concorrente)   │
└─────────────────────────────────────────────────────────────┘
```

Rede compartilhada (`comex-network`); Streamlit independe do Airflow para subir (não declara `depends_on`).

---

## 2. Layout de páginas

### Página inicial (`streamlit_app.py`)

Landing simples: título do projeto, breve descrição em PT, links pra cada dashboard, e **status do warehouse** (último mtime do `comex.duckdb`, contagem de linhas em `main_core.core_comercio`). Se o arquivo não existir, mostra mensagem amigável ("rode a DAG `comex_pipeline` no Airflow primeiro").

### `pages/1_📊_Balança_Comercial.py`

| Elemento | Fonte | Descrição |
|---|---|---|
| Filtros (sidebar) | — | Multiselect de UF (default: todas), slider de ano (range) |
| KPI top: Saldo total | `mart_balanca_comercial.saldo_fob_usd` | Soma do período filtrado, em US$ bi |
| KPI top: Corrente comércio | `vl_exp_fob_usd + vl_imp_fob_usd` | Soma, US$ bi |
| KPI top: # UFs com saldo positivo | — | Contagem |
| Chart 1 | `mart_balanca_comercial` | Linha temporal saldo mensal (3 séries: EXP, IMP, Saldo) |
| Chart 2 | `mart_balanca_comercial` | Barras horizontais: top 10 UFs por saldo no período |
| Tabela | — | Detalhamento por UF/ano com download CSV (`st.download_button`) |

### `pages/2_🏆_Top_Produtos.py`

| Elemento | Fonte | Descrição |
|---|---|---|
| Filtros (sidebar) | — | Radio EXP/IMP, slider ano único, slider rank top-N (5–50) |
| Chart 1 | `mart_top_produtos` | Barras horizontais: top-N NCMs por VL_FOB no ano selecionado |
| Chart 2 | `mart_top_produtos` agregado por SH2 | Treemap por capítulo SH (hierarquia) |
| Tabela | — | NCM, descrição PT, valor FOB, share (%) — downloadável |

**Nota de domínio (PROJECT_CONTEXT)**: NCM 27090010 (petróleo) aparece em ambas direções legitimamente — não é bug. A página deixa explícito que filtro EXP/IMP é separado.

### `pages/3_🌐_Blocos_Econômicos.py`

| Elemento | Fonte | Descrição |
|---|---|---|
| Filtros (sidebar) | — | Multiselect de bloco (MERCOSUL, UE, Ásia, …), radio EXP/IMP |
| Aviso | — | Banner `st.info`: "um país pode pertencer a múltiplos blocos — não somar entre blocos" (já documentado no schema.yml) |
| Chart 1 | `mart_blocos_economicos` | Linha temporal anual (uma série por bloco selecionado) |
| Chart 2 | `mart_blocos_economicos` | Barras empilhadas: share de cada bloco por ano |
| Tabela | — | Bloco, ano, mês, direção, valor — downloadável |

---

## 3. Estrutura de arquivos

```
dashboard/
├── Dockerfile.streamlit          # imagem slim, ~300MB
├── requirements.txt              # streamlit, duckdb, pandas, plotly (pinados)
├── streamlit_app.py              # landing + status do warehouse
├── .streamlit/
│   └── config.toml               # tema (paleta consistente com README)
├── lib/
│   ├── __init__.py
│   ├── db.py                     # get_connection() + COMEX_DB_TARGET seam
│   ├── queries.py                # SQL parametrizado por mart, com @st.cache_data
│   └── charts.py                 # helpers Plotly (paleta, layout em PT)
└── pages/
    ├── 1_📊_Balança_Comercial.py
    ├── 2_🏆_Top_Produtos.py
    └── 3_🌐_Blocos_Econômicos.py
```

### Forward-compat seam (espelhando `common/paths.py` da v0.3)

`dashboard/lib/db.py`:

```python
DB_TARGET = os.getenv("COMEX_DB_TARGET", "duckdb")  # "duckdb" | "bigquery"

@st.cache_resource
def get_connection():
    if DB_TARGET == "duckdb":
        return duckdb.connect(DUCKDB_PATH, read_only=True)
    if DB_TARGET == "bigquery":
        raise NotImplementedError("Target 'bigquery' será implementado na v1.1.")
    raise ValueError(f"COMEX_DB_TARGET inválido: {DB_TARGET!r}")
```

Custo zero, não-especulativo: o branch `bigquery` levanta `NotImplementedError`, idêntico ao padrão do `get_parquet_sink()` atual.

---

## 4. Caching strategy

| Camada | Decorator | TTL | Motivo |
|---|---|---|---|
| Conexão DuckDB | `@st.cache_resource` | infinito (lifecycle do app) | Conexão é objeto não-serializável; uma só por sessão de servidor |
| Queries de mart | `@st.cache_data(ttl=300)` | 5 min | DAG roda mensal mas dev pode triggar manual; 5min equilibra fresh vs latência interativa |
| KPIs do landing | `@st.cache_data(ttl=60)` | 1 min | Mostra "última atualização" — precisa ser mais responsivo |

Invalidação manual: botão "Atualizar dados" no sidebar de cada página chama `st.cache_data.clear()`.

---

## 5. docker-compose — alterações

Adicionar serviço (sem mexer nos demais):

```yaml
streamlit:
  build:
    context: .
    dockerfile: dashboard/Dockerfile.streamlit
  ports:
    - "8501:8501"
  environment:
    COMEX_DB_TARGET: duckdb
    COMEX_DUCKDB_PATH: /data/comex.duckdb
  volumes:
    - ./data:/data:ro          # READ-ONLY mount — proteção dupla além do read_only=True
    - ./dashboard:/app
  restart: unless-stopped
  networks:
    - comex-network
```

**Detalhes operacionais:**
- `:ro` no bind mount + `read_only=True` no DuckDB = duas camadas de proteção contra escrita acidental
- Sem `depends_on`: Streamlit pode subir sem Airflow rodando (mostra mensagem se DB não existe)
- Porta 8501 (Streamlit default); 8080 (Airflow), 8081 (dbt docs) já ocupadas — sem conflito
- Volume `./dashboard:/app` permite hot-reload em dev (Streamlit watch nativo)

---

## 6. Operacional

### Run flow

```bash
docker compose up -d streamlit       # sobe só o Streamlit (Airflow já rodando)
docker compose up -d --build         # rebuild se requirements mudou
# Acesso: http://localhost:8501
```

Hot-reload nativo do Streamlit ativo em dev — alteração em `.py` recarrega a página automaticamente graças ao bind mount.

### Failure modes

| Falha | Detecção | Resposta |
|---|---|---|
| `comex.duckdb` não existe | `os.path.exists` no landing | Banner `st.error` com instrução: "rode `comex_pipeline` no Airflow" |
| DB locked (Airflow escrevendo) | `duckdb.IOException` em `get_connection` | `st.warning` + retry após 5s; em produção raríssimo (read_only contornado pelo DuckDB internamente) |
| Mart vazio (DAG falhou parcial) | Query retorna 0 linhas | `st.info` "sem dados pro filtro selecionado" — não crashar |
| Cache corrompido | — | Botão "Atualizar dados" no sidebar |

### Wrapper script (opcional)

`scripts/streamlit.sh` no padrão de `scripts/dbt.sh` — só faz `docker compose up -d streamlit` + abre browser. **Decisão: não criar.** `docker compose up -d streamlit` já é uma linha; um wrapper seria over-engineering (vs `dbt.sh` que injeta `--profiles-dir` e `docker compose exec`).

---

## 7. Forward compat com v1.1 (BigQuery)

| Item | v0.4 (DuckDB) | v1.1 (BigQuery) | Custo da migração |
|---|---|---|---|
| Conexão | `duckdb.connect(..., read_only=True)` | `google.cloud.bigquery.Client()` | Implementar branch `bigquery` em `lib/db.py`, já estubado |
| Queries SQL | `main_marts.mart_*` | `dataset.mart_*` | `lib/queries.py` usa `f"{SCHEMA}.{table}"` — uma var |
| Paths | `/data/comex.duckdb` | n/a | irrelevante |
| Charts | Plotly | Plotly | sem mudança |
| Caching | `@st.cache_data(ttl=300)` | `@st.cache_data(ttl=3600)` (BQ tem custo por query) | um número |

**A página não muda.** Toda a lógica de SQL e visualização vive acima do seam.

---

## 8. Phased implementation

### Phase 1 — Infra mínima (target: 1 sessão)

**Goal:** App sobe, landing carrega, conexão read-only funciona.

1. `dashboard/Dockerfile.streamlit` — `python:3.11-slim` + requirements
2. `dashboard/requirements.txt` — streamlit, duckdb, pandas, plotly pinados
3. `dashboard/lib/db.py` — `get_connection()` com seam, `@st.cache_resource`
4. `dashboard/streamlit_app.py` — landing com status do warehouse (mtime, contagem `core_comercio`)
5. `docker-compose.yml` — adicionar serviço `streamlit`
6. `.streamlit/config.toml` — tema (paleta verde/amarelo discreta, sem ufanismo)
7. **Smoke test:** `docker compose up -d --build streamlit` → http://localhost:8501 carrega; landing mostra contagem real de linhas
8. **Commit:** `v0.4.0 — infra Streamlit + landing`

**Definition of done:** App responde 200, landing renderiza KPI básico do warehouse.

### Phase 2 — Dashboards (target: 1 sessão)

**Goal:** As 3 páginas funcionando com filtros, charts e download CSV.

1. `dashboard/lib/queries.py` — funções SQL parametrizadas (uma por mart usada)
2. `dashboard/lib/charts.py` — helpers Plotly (paleta, layout PT, formatação US$ bi)
3. `pages/1_📊_Balança_Comercial.py`
4. `pages/2_🏆_Top_Produtos.py`
5. `pages/3_🌐_Blocos_Econômicos.py`
6. **Validação manual:** cada filtro produz chart coerente; números batem com `query_top.py`
7. **Commit:** `v0.4.1 — 3 dashboards funcionais`

**Definition of done:** Todas as 3 páginas renderizam sem erro; filtros respondem; valores conferem com queries diretas no DuckDB.

### Phase 3 — Polish + docs (target: 1 sessão)

**Goal:** Material de portfólio (screenshots) e docs atualizados.

1. Ajuste fino de paleta e tipografia
2. Screenshots de cada dashboard → `docs/images/`
3. `README.md` — nova seção "v0.4 — Visualização" em PT com screenshots, como rodar, troubleshooting
4. `PROJECT_CONTEXT.md` — tickar checklist v0.4, adicionar "Decisões da v0.4"
5. `.gitignore` — `dashboard/.streamlit/secrets.toml` defensivo (não usado agora)
6. **Commit:** `v0.4 — Streamlit dashboards`

---

## 9. Risks & unknowns

| # | Risco | Impact | Probability | Mitigation / o que validar primeiro |
|---|---|---|---|---|
| 1 | **DuckDB read-only conflita com escrita do Airflow** — mesmo em modo read, lock pode bloquear | HIGH | LOW | Validar no smoke test: rodar `comex_pipeline` E acessar dashboard simultaneamente. DuckDB 1.0.0 doc afirma suporte a múltiplos readers + 1 writer; bind mount `:ro` é defesa adicional |
| 2 | **Streamlit hot-reload no Windows via bind mount lento** | MED | MED | Já presente no projeto (host Windows, container Linux). Tolerável em dev; usuário pode `Ctrl+R` se watcher engasgar |
| 3 | **Plotly bundle pesado (~3MB no primeiro load)** | LOW | HIGH | Aceitável pra dashboard interno. CDN do Plotly resolve em produção |
| 4 | **Caching agressivo esconde dados novos pós-DAG** | MED | MED | TTL de 5 min + botão manual de invalidação. Aceitável dado que DAG é mensal |

### Decisões fixadas (a confirmar com usuário antes de Phase 1)

| # | Pergunta | Default proposto | Reversível? |
|---|---|---|---|
| 1 | Stack de charts | **Plotly** | Sim — `lib/charts.py` isola |
| 2 | Multipage vs tabs | **Multipage** (`pages/`) | Sim, mas refactor de ~50 linhas |
| 3 | Container separado | **Sim** (`Dockerfile.streamlit` próprio) | Sim — fácil mover pra Airflow se necessário |
| 4 | Filtros: globais ou por página | **Por página** (state isolado) | Sim — `st.session_state` permite migrar |
| 5 | Wrapper `scripts/streamlit.sh` | **Não criar** (one-liner não justifica) | Sim — trivial adicionar depois |
| 6 | Paleta | **Verde/amarelo discreta** + neutros | Sim — `config.toml` é uma edição |

---

## Quality checklist

- [x] Stack escolhida com alternativas rejeitadas
- [x] Layout de cada página detalhado (filtros, KPIs, charts)
- [x] Estrutura de pastas completa
- [x] Caching strategy explícita por camada
- [x] Alterações no docker-compose isoladas (sem tocar Airflow)
- [x] v1.1 portability seam definido (`COMEX_DB_TARGET`)
- [x] Failure modes enumerados
- [x] Fases ordenadas, cada uma mergeable
- [x] 4 riscos com mitigação; 6 decisões abertas
- [x] Sob 350 linhas
- [x] Honra constraints do PLAN_V0.3.md (read-only obrigatório, sink seam, sem instalações no host, PT em docs)

---

**Next step:** Confirmar as 6 decisões da §9. Se OK, iniciar **Phase 1 step 1** — criar `dashboard/Dockerfile.streamlit`.
