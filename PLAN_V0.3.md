# PLAN v0.3 — Orquestração com Airflow

> **Confidence:** 0.92 (HIGH) — KB: project conventions explicit; MCP-equivalent: Airflow 2.9.3 TaskFlow + BashOperator are standard patterns; no novel tech.
> **Scope:** Wrap existing `ingestion/*.py` + `dbt build` in DAGs without changing model SQL or ingestion script semantics.
> **Out of scope:** GCS sink, BigQuery target, Cosmos integration, Streamlit (v0.4+), email/Slack alerting infra.

---

## 1. DAG topology

### Recommendation: **ONE end-to-end DAG**, three logical task groups

A single DAG (`comex_pipeline`) keeps lineage and SLAs unified, matches the "one pipeline" mental model of the project, and avoids the cross-DAG dependency complexity (`ExternalTaskSensor`, dataset events) that splits would force. The pipeline is short (~25 s for `dbt build`, minutes for download), so a monolithic DAG won't hurt parallelism — and `TaskGroup`s give a clean UI without the operational cost.

Rejected alternatives:

| Option | Why rejected |
|---|---|
| Two DAGs (ingest / transform) joined by `Dataset` events | Adds a coordination surface for ~25 s of compute; lineage view becomes harder to reason about |
| Per-year DAGs (DAG factory) | Year window already lives in `ingestion` flags + dbt vars; per-year DAGs explode the UI for no gain at v0.3 scale (5 years) |
| One DAG per direção (exp / imp) | Same downstream `dbt build` would have to run after both — synchronization is harder than just dynamic-mapping a single task |

### Task graph

```
                            ┌──────────────────┐
                            │ start (EmptyOp)  │
                            └────────┬─────────┘
                                     │
                ┌────────────────────┴────────────────────┐
                │            TaskGroup: ingest            │
                │                                         │
                │  ┌──────────────────────────────────┐   │
                │  │ download (BashOperator)          │   │
                │  │ python ingestion/download.py     │   │
                │  │   --anos {{ var.json.anos }}     │   │
                │  └────────────────┬─────────────────┘   │
                │                   │                     │
                │  ┌────────────────▼─────────────────┐   │
                │  │ convert (BashOperator)           │   │
                │  │ python ingestion/                │   │
                │  │   convert_to_parquet.py          │   │
                │  └────────────────┬─────────────────┘   │
                └───────────────────┼─────────────────────┘
                                    │
                ┌───────────────────┴─────────────────────┐
                │           TaskGroup: transform          │
                │                                         │
                │  ┌──────────────────────────────────┐   │
                │  │ dbt_deps (BashOperator)          │   │
                │  │ dbt deps  [skipped if no pkgs]   │   │
                │  └────────────────┬─────────────────┘   │
                │  ┌────────────────▼─────────────────┐   │
                │  │ dbt_build (BashOperator)         │   │
                │  │ dbt build --vars '{ano_inicio,   │   │
                │  │   ano_fim}' --fail-fast          │   │
                │  └────────────────┬─────────────────┘   │
                └───────────────────┼─────────────────────┘
                                    │
                            ┌───────▼──────────┐
                            │ end (EmptyOp)    │
                            └──────────────────┘
```

**Why `dbt build` (not `run` + `test`) as one task:** `build` interleaves model + tests in dependency order, fails fast on a bad test, and matches what `./scripts/dbt.sh build` already does. Splitting `run` from `test` prevents bad data from being used by downstream marts on partial failure (build short-circuits between layers; sequential run+test does not).

### Operator choice per task

| Task | Operator | Rationale | Tradeoff |
|---|---|---|---|
| `download` | `BashOperator` | Wraps existing `download.py` CLI verbatim; keeps script as single source of truth; reusable from CLI | Loses Python-level XCom of granular results; OK at v0.3 |
| `convert`  | `BashOperator` | Same reasoning as download | Same |
| `dbt_deps` | `BashOperator` | Native dbt CLI; trivial to skip if no `packages.yml` | None at this scale |
| `dbt_build`| `BashOperator` | Direct `dbt build` invocation; matches `scripts/dbt.sh` pattern | `astronomer-cosmos` would parse the manifest into per-model tasks (great lineage in Airflow UI) but adds a heavy dep, requires manifest at parse time, and the project only has 15 models — **not justified at v0.3**. Revisit at v1.1 |
| `start` / `end` | `EmptyOperator` | Standard anchors for `TaskGroup` boundaries | None |

**TaskFlow API (`@dag` / `@task`)** is used for the **wiring file** (clean Python, automatic XCom). Each unit of work is still a `BashOperator` invocation because the underlying scripts are CLIs — wrapping them in `@task` would add a Python layer that buys nothing. TaskFlow earns its keep when we add Python-only helpers in Phase 2 (e.g., manifest → KPI XCom).

### `astronomer-cosmos` decision (deferred)

| Criterion | v0.3 verdict |
|---|---|
| Model count | 15 — too few to need per-model UI |
| Test surface | 60 tests run in ~25 s — granular UI not worth parse-time cost |
| Manifest dependency | Cosmos requires `manifest.json` at DAG parse — adds a build step before Airflow starts |
| **Decision** | **Defer to v1.1** when BigQuery latency makes per-model retries valuable |

---

## 2. Scheduling & idempotency

### Schedule

| Setting | Value | Rationale |
|---|---|---|
| `schedule` | `"0 6 25 * *"` (06:00 BRT, day 25 of every month) | MDIC publishes around the 15th; +10 day buffer for late publishes; off-peak local time (confirmed by user) |
| `start_date` | `pendulum.datetime(2026, 1, 1, tz="America/Sao_Paulo")` | Past-anchored; fixed (do not use `days_ago`) |
| `catchup` | `False` | We refresh the rolling window each run; backfilling 5 years monthly = wasted compute |
| `max_active_runs` | `1` | Single DuckDB file — concurrent writes would corrupt; also avoids hammering MDIC |
| `default_args.depends_on_past` | `False` | Each run is a snapshot; one bad run shouldn't block the next |
| `tags` | `["comex", "v0.3", "monthly"]` | Filterable in UI |
| `dagrun_timeout` | `timedelta(hours=2)` | Generous — full download from cold can take ~1 h on slow link |

### Idempotency strategy

The pipeline is **idempotent by design** because every component already is:

| Component | Idempotency mechanism | DAG behavior |
|---|---|---|
| `download.py` | Skips files that already exist on disk; `--force` bypasses | Default DAG runs **without** `--force`; manual `dagrun conf` can pass `force: true` |
| `convert_to_parquet.py` | Same: skip if `.parquet` exists | Same |
| `dbt build` | All models are `view` or `table` (full refresh) → re-running overwrites | Run every time; cheap (~25 s) |

**Forced re-download for the current/previous month:** The current-month CSV from MDIC grows during the month (incremental publish). To capture updates, the DAG **always re-downloads the current calendar year and the previous one** with `--force`, while older years are left alone. This is implemented by passing `--anos {ano_atual-1} {ano_atual}` to a second `download_recent_force` task that runs alongside the regular `download` for the full window.

Simpler v0.3 alternative (recommended for first cut): **always run `--force` on the full window**. The hot path is ~5 yearly files at 100–500 MB each — a few minutes off-peak. Defer the split to Phase 2 if it hurts.

### Year window: how to parameterize

Three sources of truth needed: ingestion CLI flag (`--anos`), dbt vars (`ano_inicio` / `ano_fim`), and DAG default. **Single source: Airflow Variables**, JSON-typed.

| Variable | Type | Default | Used by |
|---|---|---|---|
| `comex_anos` | JSON list `[2020, 2021, 2022, 2023, 2024]` | seeded on first deploy | `download` + `convert` tasks |
| `comex_dbt_vars` | JSON `{"ano_inicio": 2020, "ano_fim": 2024}` | seeded on first deploy | `dbt_build` task (`--vars` flag) |

**Why Variables (not env vars or hardcoded):**
- Editable from Airflow UI without redeploy
- Per-environment override (dev / prod will diverge in v1.1)
- `dagrun.conf` can override at trigger time for ad-hoc backfills (`{"anos": [2024]}`) without touching the variable

**Per-run override pattern:** Each task resolves its window as `dagrun.conf.get('anos') or Variable.get('comex_anos', deserialize_json=True)`. Encapsulated in the `common/config.py` helper (see §4).

---

## 3. Operational concerns

### Retry & timeout policy

| Task | retries | retry_delay | execution_timeout | Reasoning |
|---|---|---|---|---|
| `download` | 3 | `timedelta(minutes=5)` | `timedelta(minutes=90)` | Network-bound; MDIC sometimes 502s; 5-min backoff lets transients clear |
| `convert`  | 1 | `timedelta(minutes=2)` | `timedelta(minutes=30)` | CPU-bound; failure usually means corrupt CSV — retry once in case of transient I/O |
| `dbt_deps` | 0 | — | `timedelta(minutes=5)` | Deterministic; failure means config bug, retrying won't help |
| `dbt_build`| 0 | — | `timedelta(minutes=15)` | A dbt test failure is a **data** problem; retrying re-fails. Surface immediately |
| `start`/`end` | 0 | — | — | EmptyOperator |

`retry_exponential_backoff=True` for `download` only. All tasks set `email_on_failure=False` (no SMTP configured in v0.3).

### Logging

The existing scripts use a mix of `logging` (good) and `print()` for the progress bar (acceptable). **Do not change the scripts.** Airflow's `BashOperator` captures stdout+stderr verbatim — the logs land in Airflow task logs automatically. The progress bar (`\r` carriage returns) will look noisy in the file-backed Airflow log but won't break anything.

If we want cleaner Airflow logs later, add `--quiet` flag to the scripts (Phase 3) — not v0.3.

### Failure modes & responses

| Failure mode | Detection | Response |
|---|---|---|
| Partial CSV download (network drop mid-stream) | `download.py` already deletes the partial file on `RequestException` and exits non-zero | BashOperator marks task failed → retry kicks in (3 attempts) |
| MDIC site down (503 / DNS fail) | `requests` raises; non-zero exit | Same retry; if all 3 fail, task fails red → next month's run picks it up. **No alerting in v0.3** |
| Parquet conversion fails mid-year | `_converter_csv` deletes partial Parquet, returns False, but **the script still exits 0** if any other file converted | **Risk** — see §7. Mitigation: `convert_to_parquet.py` should exit non-zero on any failure. Small patch in Phase 1 |
| `dbt test` failure (e.g., a `not_null` breaks) | `dbt build --fail-fast` exits non-zero; downstream marts skipped | Task fails red. Data is **not silently corrupted** because failed test stops the build before marts |
| DuckDB file locked (concurrent run) | DuckDB raises `IOException` | `max_active_runs=1` prevents this. If it happens (e.g., manual `dbt build` during scheduled run), task fails — acceptable |
| Disk full | Both scripts raise `OSError` | Task fails. **No automated cleanup in v0.3** — operator runbook task |

### Sensors

**Recommendation: NO sensor in v0.3.** Defer to Phase 3.

Rationale:
- An `HttpSensor` against `balanca.economia.gov.br` only confirms the *site* is up, not that *new monthly data* has been published (no public manifest endpoint, only files)
- A `HEAD` request on the current-year CSV could check `Last-Modified`, but the file changes every day intra-month — would always trigger
- Schedule + `--force` on recent years already gives the right behavior

If we later want a true "wait for new data" gate, the right shape is a custom sensor that compares `Last-Modified` of `EXP_{ano_atual}.csv` to a stored XCom from the previous run. **Phase 3 work.**

---

## 4. Files to create

| Path | Purpose |
|---|---|
| `airflow/dags/comex_pipeline.py` | Main DAG: `@dag` decorator, three TaskGroups (`ingest`, `transform`), default_args, schedule |
| `airflow/dags/common/__init__.py` | Marks `common` as a package importable from DAG file |
| `airflow/dags/common/config.py` | `get_anos()`, `get_dbt_vars()` helpers — read Airflow Variables with `dagrun.conf` override; centralizes parameter resolution |
| `airflow/dags/common/paths.py` | Constants for container paths (`INGESTION_DIR=/opt/airflow/ingestion`, `DBT_DIR=/opt/airflow/dbt`, `DATA_DIR=/opt/airflow/data`); avoids string-literal drift |
| `airflow/dags/common/bash_commands.py` | Bash command **builders** (Python functions returning strings) for `download`, `convert`, `dbt build`. Keeps the DAG file declarative and the commands unit-testable |
| `airflow/plugins/.gitkeep` | Placeholder; no plugins in v0.3 |
| `scripts/seed_airflow_variables.sh` | One-shot helper: runs `airflow variables import` inside the scheduler container with `airflow/variables.json` |
| `airflow/variables.json` | Seed file: `{"comex_anos": [2020,...,2024], "comex_dbt_vars": {...}}`. Versioned for reproducibility |
| `airflow/dags/README.md` | Portuguese — short doc explaining the DAG, how to trigger manually, how to override `anos` via `dagrun conf` |

### Updates to existing files

| File | Change | Reason |
|---|---|---|
| `ingestion/convert_to_parquet.py` | Make `executar()` return non-zero / raise if **any** file fails (currently per-file failure is logged but `main()` exits 0) | Surface partial failures to Airflow; prerequisite for reliable retries |
| `ingestion/download.py` | Same — `executar()` should propagate per-file failures to exit code | Same |
| `Dockerfile.airflow` | **No change.** All deps already present | — |
| `ingestion/requirements.txt` | **No change.** Airflow itself comes from base image | — |
| `docker-compose.yml` | **No change.** `./airflow/dags` and `./airflow/plugins` are already mounted | — |
| `README.md` | Add a "v0.3 — Orquestração" section in Portuguese: how to start the DAG, schedule, manual trigger | User-facing docs |
| `PROJECT_CONTEXT.md` | Tick v0.3 checklist; append "decisões da v0.3" mini-section | Maintain context history |
| `.gitignore` | Add `airflow/logs/` defensively (already a named volume, but if someone bind-mounts it...) | Hygiene |

**File count:** 9 new + 4 modified. No new Docker images, no new services.

---

## 5. Forward compatibility with v1.1 (GCP / BigQuery)

The DAG must remain **storage- and warehouse-agnostic** at the orchestration layer. Concretely:

### What the DAG must NOT assume

| Assumption to avoid | Why | How to enforce in v0.3 |
|---|---|---|
| dbt target is `duckdb` | v1.1 will pass `--target bigquery` | DAG must accept a `dbt_target` parameter (default `duckdb`); `dbt_build` task uses `--target {{ var.value.comex_dbt_target }}` |
| Parquet sink is local FS | v1.1 sink will be `gs://comex-brasil-raw/parquet/...` | Wrap "where do parquet files go" in `common/paths.py` with a `get_parquet_sink()` function that returns a string. v0.3 returns local path; v1.1 returns a `gs://` URI passed to a swapped writer |
| Download writes to local FS | Same as above | Same. `download.py` is allowed to keep writing local in v0.3 — the **DAG-level abstraction** is what matters |
| The `airflow-scheduler` container is the executor | v1.1 may use Cloud Composer (Celery/Kubernetes executor) | `BashOperator` works on any executor; **avoid** `LocalFilesystemBackend` or anything that assumes a specific worker FS |
| DuckDB-specific dbt vars/macros | Models are SQL-pure already (per CLAUDE.md) | Don't add DuckDB-only `--vars` from the DAG; keep `--vars` to the year window only |

### Sink swap design (cheap, not over-engineered)

Add a single env-var-driven branch in `common/paths.py`:

```
SINK = os.getenv("COMEX_SINK", "local")  # "local" | "gcs"
```

- v0.3: `SINK=local` — `convert_to_parquet.py` writes to `/opt/airflow/data/parquet/`; dbt `external_location` reads same path
- v1.1: `SINK=gcs` — a v1.1-specific writer (Polars + `gs://` via `gcsfs`) is selected; dbt `external_location` updates to `gs://...` (one-line change in `sources.yml`)

**No actual GCS code in v0.3** — just the env-var seam. The cost is one `if SINK == "gcs"` stub raising `NotImplementedError`. Future-proofing without speculative complexity.

### dbt portability checklist (already mostly satisfied)

| Item | Status |
|---|---|
| `profiles.yml` has `bigquery` placeholder | Present |
| Models avoid DuckDB-only SQL | Enforced by CLAUDE.md (`read_parquet()` only in `sources.yml`) |
| Year window via vars (not hardcoded) | Already `{ano_inicio, ano_fim}` |
| DAG passes `--target` explicitly | **To do in v0.3** |

---

## 6. Phased implementation

Each phase is independently mergeable and produces a working pipeline.

### Phase 1 — Minimal end-to-end DAG (target: 1 session)

**Goal:** Green DAG run that does the same thing as the current manual workflow.

1. Patch `ingestion/download.py` and `convert_to_parquet.py` to propagate failures to exit code.
2. Create `airflow/dags/common/{__init__.py, paths.py, config.py, bash_commands.py}`.
3. Create `airflow/variables.json` + `scripts/seed_airflow_variables.sh`.
4. Create `airflow/dags/comex_pipeline.py` with TaskFlow `@dag`, `EmptyOperator`s, two TaskGroups, `BashOperator`s.
5. Smoke test: `docker compose up -d`, seed variables, trigger DAG manually from UI, confirm green run end-to-end.
6. Update `README.md` (Portuguese) and `PROJECT_CONTEXT.md`. Tag commit `v0.3.0`.

**Definition of done:** DAG runs green from UI; `dbt build` produces same 15 tables and 60 passing tests as today.

### Phase 2 — Operational hardening (target: 1 session)

**Goal:** Production-quality observability and idempotency control.

1. ~~Split `download` into `download_full_window` + `download_recent_force`~~ — **dropped** (decision #4: full-window `--force` stays as the default).
2. Add `dagrun.conf` override for `anos` (manual backfill ergonomics).
3. Add `dbt_target` Airflow Variable; pass `--target` to `dbt_build`. Default `duckdb`.
4. Add `airflow/dags/README.md` explaining manual trigger, conf overrides, and how to skip ingestion (`{"skip_ingest": true}`).
5. Add Airflow `tags` filter, `description`, `doc_md` on the DAG.
6. Tag commit `v0.3.1`.

### Phase 3 — Sensors & alerting (optional, deferable to v0.4)

1. Custom `MdicLastModifiedSensor` (PythonOperator wrapping a `HEAD` request, comparing `Last-Modified` to last-run XCom).
2. `on_failure_callback` posting to a webhook (Discord / Slack) — requires user to provide a URL.
3. SLA monitoring: `sla=timedelta(hours=3)` on `dbt_build`.

**Phase 3 is explicitly NOT v0.3.** Listed for roadmap clarity only.

---

## 7. Risks & unknowns

### Top 3 risks

| # | Risk | Impact | Probability | Mitigation / what to validate first |
|---|---|---|---|---|
| 1 | **`convert_to_parquet.py` swallows per-file errors** — partial failures silently produce green DAG runs with missing Parquet | HIGH (data loss is invisible) | MED | **Validate first**: read both `executar()` functions and confirm exit codes. Patch in Phase 1 step 1 before any DAG work |
| 2 | **DuckDB file lock contention** — manual `./scripts/dbt.sh build` during a scheduled DAG run corrupts or hangs | HIGH (corruption) | LOW | `max_active_runs=1` on the DAG handles intra-DAG; **runbook entry** in `airflow/dags/README.md` warns operators not to run `dbt.sh` while DAG is active. Long-term fix is BigQuery (v1.1) |
| 3 | **MDIC current-year CSV grows mid-month** — without `--force` on recent years, we capture stale snapshots | MED (stale data) | HIGH | Phase 2 adds `download_recent_force`. v0.3 Phase 1 ships with full-window `--force` as the safe default; revisit cost after first month |

### Decisions (answered 2026-04-24)

| # | Question | Decision | Impact on plan |
|---|---|---|---|
| 1 | Schedule | **`0 6 25 * *` BRT** (06:00, day 25) | Updated §3. +10-day buffer after MDIC's ~day-15 publish |
| 2 | Year window evolution | **Manual** — update `comex_anos` Variable when a new year is ready | No rolling-window code in v0.3; no cron for Dec→Jan transition |
| 3 | Alerting in v0.3 | **Postponed** — revisit later (maybe v0.4+) | Phase 3 stays fully deferred; no webhook, no SLA, no on-failure callback |
| 4 | `--force` strategy | **`--force` on full window by default** | Phase 2 step 1 (split into `download_full_window` + `download_recent_force`) is removed from scope; simplifies Phase 2 |
| 5 | Cosmos (per-model Airflow tasks) | **Defer to v1.1** | Phase 1 uses single `dbt_build` BashOperator; no `astronomer-cosmos` dependency added now |

---

## Quality checklist

- [x] Requirements clear (wrap existing scripts, keep dbt portable, no host installs)
- [x] Constraints documented (LocalExecutor, Linux container, no MSYS path issues, Latin-1 inside scripts)
- [x] One DAG topology recommended with rejected alternatives
- [x] Operator choice justified per task
- [x] Schedule + idempotency designed
- [x] Retry / timeout matrix per task
- [x] Failure modes enumerated with responses
- [x] File inventory complete (paths absolute / repo-relative, purposes single-line)
- [x] v1.1 portability seam defined (env-var + paths helper)
- [x] Phases ordered, each independently mergeable
- [x] Top 3 risks with mitigation; 5 open questions
- [x] Under 500 lines

---

**Next step:** All 5 open questions answered (see §7 Decisions, 2026-04-24). Start **Phase 1 step 1** — patch `ingestion/download.py` and `ingestion/convert_to_parquet.py` to propagate per-file failures to the process exit code. This unblocks every downstream DAG task.
