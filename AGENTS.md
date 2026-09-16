# LexRisk — working notes for agents

Only non-obvious things live here. Manifests cover the rest.

## Running it

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

- `api` = FastAPI (`backend/main.py`) on host port **3000**, container port 8000, `uvicorn --reload`
  over a bind mount, so source edits apply live. Interactive test surface: **`/docs`**.
- Health: `GET /api/v1/health`. Endpoints: `POST /api/v1/analyze`, `GET /api/v1/usage`.
- `migrate` is a one-shot service running `schema.sql` through psql. `schema.sql` is
  idempotent, so re-running it is the way to apply schema changes:
  `docker compose -f docker-compose.base44.yml run --rm migrate`.

## Quirks that will bite you

- **The API container deliberately does NOT install torch / sentence-transformers**
  (`backend/requirements-api.txt` is a slim profile; root `requirements.txt` is the full one).
  It runs with `ENABLE_NLP_FILTER=false`. `nlp_engine.py` imports the ML stack behind a
  try/except and raises a clear error only if you construct the engine without it.
- **No LLM key = HTTP 503 on `/analyze`, not a crash.** `.env.base44-defaults` holds a
  placeholder `GROQ_API_KEY` purely so the process boots; real keys arrive via
  `/run/base44/app.env`, listed last in compose so they always win. `llm_configured: true`
  in `/health` only means a key is *present*, not that it is valid.
- **Caller identity is a plaintext `X-User-Id` header** (`backend/deps.py`) until JWT auth
  lands. Do not expose this API publicly before then.
- **Quota is charged on cache hits too** (audit FIX 5). `analysis_history.cache_hit`
  records the ratio. Don't "optimise" the increment away.
- `check_daily_limit()` in `schema.sql` previously returned NULLs for any user with no
  usage row today (blocking every first request) because `SELECT ... INTO` leaves the
  variable NULL when no row matches. The COALESCE must wrap the whole subquery.
- Two stale `TIER_LIMITS` python dicts are quarantined with warnings; `tier_limits` in
  Postgres is the source of truth.
- `telemetry.py` is broken-since-creation — do not import it.

## Tests

```bash
python -m pytest -q          # 43 pass, 4 integration skipped
python -m pytest -m integration   # needs a REAL GROQ_API_KEY
```

`tests/conftest.py` stubs only genuinely-missing heavy deps (torch, SDKs, psycopg2) so the
suite runs in a bare container; real packages are always preferred. `tests/test_backend_api.py`
stubs the DB + analyzer and asserts the HTTP contract only.
