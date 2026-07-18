# KSP Crime Intelligence Platform

Conversational AI and crime analytics over the Karnataka State Police FIR database.
**Datathon 2026 — Problem Statement 1.**

---

## Quick start

```bash
cp .env.example .env      # then add your ANTHROPIC_API_KEY
make up
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend health | http://localhost:8000/health/db |
| API docs | http://localhost:8000/docs |
| Postgres | `localhost:5432` (`make psql`) |

```bash
make reset    # wipe the database volume and re-run db/init/*.sql
make test     # backend test suite
make tables   # list both schemas
make help     # all targets
```

---

## What this is

The KSP FIR schema has **no person entity**. `Accused.AccusedMasterID` is a row ID scoped to a
single FIR — nothing in the supplied schema says two FIRs involve the same human being. Every
question about repeat offenders, criminal networks, or gangs is therefore uncomputable until
that identity layer is built.

Building it is the centre of this project. Everything else — the conversational interface,
network analysis, MO fingerprinting, risk scoring — sits on top of `derived.person_cluster`.

**Read [`PLAN.md`](PLAN.md)** for the full reasoning and feature plan.

---

## Documents

| File | Purpose |
|---|---|
| [`PLAN.md`](PLAN.md) | Architecture, ER engine design, tool catalog, scope boundaries, demo script |
| [`PROMPTS.md`](PROMPTS.md) | 33 Claude Code prompts in execution order |
| [`CLAUDE.md`](CLAUDE.md) | Auto-loaded context + non-negotiable rules for every session |
| [`CONSISTENCY.md`](CONSISTENCY.md) | **Shared build log — read before starting, update before stopping** |

---

## Architecture

```
Postgres 16 + PostGIS + pgvector
  ├── schema  ksp        source tables, read-only
  └── schema  derived    person_cluster, MO clusters, alerts, audit log
        ↓
  entity resolution (backend/er/)   ← the core engine
        ↓
  tool layer (backend/app/tools/)   ~25 typed, RBAC-checked, audit-logged functions
        ↓
  orchestration (backend/app/api/)  Claude tool-calling loop
        ↓
  frontend/                          chat · map · network graph · evidence
```

### Non-negotiable rules

1. The LLM **never writes SQL** — it selects from the typed tool catalog.
2. The LLM **never authors a fact** — every claim comes from a tool result, or the system says
   it cannot answer.
3. Every tool returns **provenance** (`sql_hash`, `row_ids`, `crime_nos`).
4. RBAC is enforced at the **tool boundary**, never in the prompt.
5. Every tool call is **audit-logged** — the audit trail and the evidence trail are one artifact.
6. We predict **places, times, and case outcomes — never people.**

---

## Working with a teammate

1. Read [`CONSISTENCY.md`](CONSISTENCY.md).
2. Claim your prompt on the Claim Board, commit that change **first**.
3. Build. Verify against the prompt's acceptance criteria.
4. Append a session entry to `CONSISTENCY.md` and commit it **separately** from code.

Commit `CONSISTENCY.md` on its own — it's append-only, so conflicts always resolve to
"keep both sides."

---

## Status

Phase 0 in progress. See the status table in [`CONSISTENCY.md`](CONSISTENCY.md).
