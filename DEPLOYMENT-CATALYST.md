# Deploying on Zoho Catalyst

Zoho Catalyst is the hackathon's platform partner, so hosting and platform services are
mapped onto Catalyst wherever a Catalyst service can genuinely carry them. This document is
the deployment contract: what runs where, which env vars configure it, and the one thing
that deliberately stays off-Catalyst (and why).

## Service mapping

| Component | Runs on | Notes |
|---|---|---|
| FastAPI backend (`backend/`) | **Catalyst AppSail** | Managed `python_3_12` runtime, or the existing Dockerfile as a custom OCI runtime (linux/amd64). Entry: `python serve.py` — binds `X_ZOHO_CATALYST_LISTEN_PORT` (mandatory; instance is killed if not bound in 10 s). |
| LLM access | **Catalyst QuickML LLM Serving** (BYOK) | The orchestration loop's default provider — Catalyst's own hosted LLMs (Qwen 2.5). Configure the model's endpoint + the key from the Catalyst console; no provider SDK needed. See "LLM on Catalyst" below. |
| React frontend (`frontend/`, P19) | **Catalyst Slate** | Static SPA hosting; deploy via `catalyst deploy` or Git. Add the Slate origin to the backend's `CORS_ORIGINS`. |
| Scheduled alerts (P17a) | **Catalyst Job Scheduling** | Cron-style jobs targeting the AppSail service's alert endpoint — replaces a host-side cron. |
| PDF export (P24) | **Catalyst SmartBrowz** | Server-side PDF/screenshot generation — first choice before falling back to WeasyPrint in-process. |
| Report/file storage (P24) | **Catalyst Stratus** | Object storage + signed URLs for generated PDFs/exports. |
| Hot lookups / rate limiting | **Catalyst Cache** | Optional; in-memory KV with TTL. |
| End-user auth (post-demo) | **Catalyst Authentication** | The demo passes the principal in the request body; RBAC is enforced at the tool boundary regardless, so Catalyst auth slots in front without touching tool code. |
| Postgres 16 + PostGIS + pgvector | **External** (compose / managed Postgres) | See below — the one deliberate exception. |

### Why the database stays Postgres (the one exception)

Catalyst Data Store is a relational store queried via ZCQL, but this project's core is
unimplementable on it: the ER pipeline and RBAC scope resolution need **recursive CTEs**
(`unit.parent_unit` subtree), the geo features need **PostGIS**, semantic search needs
**pgvector**, and fuzzy matching needs **pg_trgm** — none of which ZCQL provides. The
`ksp`/`derived` two-schema design, 29-table source schema, and COPY-based bulk loads are
likewise Postgres-native. So the database runs as external Postgres (docker compose for the
demo; any managed Postgres for a longer-lived deployment) and AppSail connects to it over
`POSTGRES_HOST`/`POSTGRES_PORT`. Everything above the database is Catalyst.

## LLM on Catalyst

Catalyst is the only cloud, so the LLM is Catalyst's own: **QuickML LLM Serving** (Qwen 2.5
— 14B Instruct, 7B Coder, 7B Vision), served from a per-model POST endpoint with Zoho OAuth.
Deploy/select a model in QuickML, then read its endpoint + key from the model's **API
Details** panel and configure:

```
LLM_PROVIDER=uniai
UNIAI_BASE_URL=<endpoint URL from the model's API Details>
UNIAI_API_KEY=<OAuth access token / key from the Catalyst console>
UNIAI_MODEL=<model id, e.g. qwen2.5-14b-instruct>
UNIAI_CHAT_PATH=/v1/chat/completions   # set to "" if the endpoint URL is already complete
UNIAI_AUTH_SCHEME=zoho-oauthtoken       # QuickML uses Zoho OAuth; "bearer" for plain gateways
UNIAI_TOOL_MODE=prompted                # see below
```

### Tool calling: `prompted` (default) vs `native`

The platform depends on the model **selecting typed tools** (the LLM never writes SQL, never
authors a fact). Whether Catalyst's serving endpoint exposes OpenAI-style function calling is
undocumented, so the client supports two modes and **defaults to the one that always works**:

- **`prompted`** (default) — the tool catalogue and a strict JSON protocol are injected into
  the system prompt; the model replies with `{"tool": ...}` or `{"final": ...}`, which the
  client parses. Works with **any** chat model, including a plain Qwen deployment with no
  tool-calling API. This is the safe Catalyst default.
- **`native`** — sends OpenAI `tools` and reads `tool_calls`. Better quality; set
  `UNIAI_TOOL_MODE=native` only after confirming the endpoint supports it.

### Day-one verification (the moment the model + key exist)

```
export UNIAI_BASE_URL=... UNIAI_API_KEY=... UNIAI_MODEL=... UNIAI_AUTH_SCHEME=zoho-oauthtoken
cd backend && python -m app.api.run_eval --live
```

That runs the full 28-question eval (tool routing, RBAC denials, refusal cases) against the
live Catalyst model and prints a pass rate, then a multi-turn transcript. If auth/path
differ, `UNIAI_CHAT_PATH` / `UNIAI_AUTH_SCHEME` are the knobs; try `native` if the model
supports it; if the request/response body differs materially from OpenAI's, only
`OpenAICompatClient` needs adapting — the orchestrator, tools, and eval are untouched.

Fallback: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` uses the direct Anthropic SDK path
(`claude-opus-4-8`) — for local comparison only; not a Catalyst deployment.

## Deploying the backend to AppSail

Prereqs: `npm i -g zcatalyst-cli`, then `catalyst login` and `catalyst init` in the repo.

**Option A — managed runtime, standalone deploy (recommended: secrets stay in the console).**

```
catalyst deploy appsail \
  --name ksp-backend \
  --build-path /absolute/path/to/repo/backend \
  --stack python_3_12 \
  --command "python serve.py"
```

Use an **absolute** `--build-path` (relative paths deploy but fail at runtime). Then set the
env vars (UNIAI_*, POSTGRES_*, CORS_ORIGINS) in Console → AppSail → Configuration →
Environment Variables.

**Option B — linked app via `backend/app-config.json`.** Run `catalyst appsail:add` once,
then `catalyst deploy appsail --name ksp-backend`. Caveat: for linked apps the
`env_variables` block in `app-config.json` is the source of truth — console-set values are
**removed on every redeploy** if not listed there. Our `app-config.json` deliberately omits
`env_variables` so no secret ever lands in git; prefer Option A if you want console-managed
secrets.

**Option C — Docker custom runtime.** The existing `backend/Dockerfile` already binds the
Catalyst port via `serve.py`:

```
docker build --platform linux/amd64 -t ksp-backend:latest backend/
catalyst deploy appsail --name ksp-backend --source docker://ksp-backend:latest
```

Memory: 1024 MB configured (256–2048 allowed) — the ER/name-parsing libraries and
SQLAlchemy pool want headroom above the 512 default.

## Environment variables (backend)

| Var | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `uniai` | `uniai` (Catalyst-hosted LLM) or `anthropic` |
| `UNIAI_BASE_URL` / `UNIAI_API_KEY` / `UNIAI_MODEL` | — | Catalyst QuickML LLM Serving endpoint + BYOK key |
| `UNIAI_CHAT_PATH` | `/v1/chat/completions` | Path suffix; set `""` if the endpoint URL is complete |
| `UNIAI_AUTH_SCHEME` | `bearer` | `bearer` or `zoho-oauthtoken` (QuickML) |
| `UNIAI_TOOL_MODE` | `prompted` | `prompted` (any model) or `native` (endpoint must support tools) |
| `ANTHROPIC_API_KEY` | — | Only for `LLM_PROVIDER=anthropic` |
| `POSTGRES_HOST` … `POSTGRES_PORT` | compose defaults | External Postgres location |
| `CORS_ORIGINS` | localhost:5173 | Comma-separated; add the Slate domain |
| `X_ZOHO_CATALYST_LISTEN_PORT` | *(injected)* | Set by AppSail; never set manually |

Do not name custom vars with a `CATALYST` prefix — Catalyst injects its own and collisions
are undefined.
