# Deploying on Zoho Catalyst

Zoho Catalyst is the hackathon's platform partner, so hosting and platform services are
mapped onto Catalyst wherever a Catalyst service can genuinely carry them. This document is
the deployment contract: what runs where, which env vars configure it, and the one thing
that deliberately stays off-Catalyst (and why).

## Service mapping

| Component | Runs on | Notes |
|---|---|---|
| FastAPI backend (`backend/`) | **Catalyst AppSail** | Managed `python_3_12` runtime, or the existing Dockerfile as a custom OCI runtime (linux/amd64). Entry: `python serve.py` — binds `X_ZOHO_CATALYST_LISTEN_PORT` (mandatory; instance is killed if not bound in 10 s). |
| LLM access | **Catalyst UniAI** (BYOK) | The orchestration loop's default provider. Configure the gateway endpoint + the key issued in the Catalyst console; no provider SDK needed. See "LLM via Catalyst UniAI" below. |
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

## LLM via Catalyst UniAI

The backend's LLM boundary (`app/api/llm.py`) is provider-agnostic. `LLM_PROVIDER=uniai`
(the default) uses `OpenAICompatClient`, which speaks the OpenAI chat-completions wire
format — including function/tool calling, which the orchestration loop requires — against
any compatible gateway endpoint:

```
LLM_PROVIDER=uniai
UNIAI_BASE_URL=<gateway base URL from the Catalyst console>
UNIAI_API_KEY=<key issued in the Catalyst console>
UNIAI_MODEL=<model id as named by the gateway>
UNIAI_CHAT_PATH=/v1/chat/completions        # override if the gateway differs
UNIAI_AUTH_SCHEME=bearer                    # or zoho-oauthtoken
```

**Day-one verification (do this the moment the hackathon key is issued):** UniAI's exact
wire format is not publicly documented, so the client assumes the OpenAI-compatible shape
that unified gateways (and Catalyst QuickML LLM serving) expose. Verify with:

```
export UNIAI_BASE_URL=... UNIAI_API_KEY=... UNIAI_MODEL=...
cd backend && python -m app.api.run_eval --live
```

That runs the full 28-question eval (tool routing, RBAC denials, refusal cases) against the
gateway and prints a pass rate. If the endpoint/auth differs, `UNIAI_CHAT_PATH` and
`UNIAI_AUTH_SCHEME` are the knobs; if the format differs materially, only
`OpenAICompatClient` needs adapting — the orchestrator, tools, and eval are untouched.

**Tool calling is required.** The whole platform depends on the model selecting typed tools
(the LLM never writes SQL, never authors a fact). When choosing the model in UniAI, pick one
with function-calling support.

Fallback: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` uses the direct Anthropic SDK path
(`claude-opus-4-8`), unchanged.

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
| `LLM_PROVIDER` | `uniai` | `uniai` (Catalyst gateway) or `anthropic` |
| `UNIAI_BASE_URL` / `UNIAI_API_KEY` / `UNIAI_MODEL` | — | Catalyst UniAI gateway + BYOK key |
| `UNIAI_CHAT_PATH` | `/v1/chat/completions` | Gateway path override |
| `UNIAI_AUTH_SCHEME` | `bearer` | `bearer` or `zoho-oauthtoken` |
| `ANTHROPIC_API_KEY` | — | Only for `LLM_PROVIDER=anthropic` |
| `POSTGRES_HOST` … `POSTGRES_PORT` | compose defaults | External Postgres location |
| `CORS_ORIGINS` | localhost:5173 | Comma-separated; add the Slate domain |
| `X_ZOHO_CATALYST_LISTEN_PORT` | *(injected)* | Set by AppSail; never set manually |

Do not name custom vars with a `CATALYST` prefix — Catalyst injects its own and collisions
are undefined.
