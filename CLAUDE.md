# KSP Crime Intelligence Platform

Conversational AI + crime analytics over the Karnataka State Police FIR database.
Datathon 2026, Problem Statement 1.

**Read `PLAN.md` for full context before any non-trivial task.** This file is the summary
that every session needs; `PLAN.md` is the reasoning behind it.

---

## ⚠️ Two developers share this repo — session protocol

**At the start of every session: read `CONSISTENCY.md`.** It records what the other developer
has already built, what broke, and what the real data turned out to look like. It **overrides**
`PLAN.md` and `PROMPTS.md` wherever they disagree — those describe the plan, `CONSISTENCY.md`
describes reality.

**Before writing code for a prompt:** check the Claim Board in `CONSISTENCY.md`. If the other
developer has claimed it, stop and tell the user rather than building it twice. If it's free,
add the claim and commit that change first.

**At the end of every session, or whenever work is paused:** append a session entry to
`CONSISTENCY.md` using the documented format, and update the prompt status table. If you
discovered something surprising about the data, or made a decision that departs from `PLAN.md`,
add it to the relevant section too — not only the session log. Commit `CONSISTENCY.md`
separately from code changes.

Do this without being asked. A session that builds something and doesn't log it has created a
merge conflict for someone else.

---

## The central fact about this database

`Accused.AccusedMasterID` is a **row ID scoped to a single FIR**, not a person identifier.
The same is true of `Victim` and `ComplainantDetails`. **There is no person entity anywhere
in the supplied schema.**

Therefore: never join on `AccusedMasterID` to find "the same person." Always join on
`person_cluster.person_cluster_id`, produced by our entity resolution pipeline. Any code that
treats `AccusedMasterID` as a stable person identity is a bug.

---

## Non-negotiable architecture rules

1. **The LLM never writes SQL.** It selects from the typed tool catalog in `app/tools/`.
   All SQL is parameterized and lives inside tool implementations.
2. **The LLM never authors a fact.** Every number, name, date, and claim in a response must
   come from a tool result. If no tool can answer, the system says so explicitly. It does not
   estimate, infer, or fill gaps.
3. **Every tool returns provenance.** `{data, provenance: {sql_hash, row_ids, crime_nos}}`.
   No exceptions — the provenance trail is how we satisfy the explainability requirement.
4. **RBAC is enforced at the tool boundary, never in the prompt.** Every tool takes a
   `principal` and filters accordingly.
5. **Every tool call is audit-logged.** The audit log and the evidence trail are the same
   artifact.
6. **We predict places, times, and case outcomes. Never people.** No individual-level crime
   prediction, ever. Offender risk scores only prioritize *existing open cases*.

---

## Stack

- Postgres 16 + PostGIS + pgvector (single database covers relational, geo, vector)
- Graph: **networkx in-memory**, not Neo4j — datathon scale, renders identically, no sync
- FastAPI + Pydantic (tool params are Pydantic models)
- LLM: `claude-opus-4-8` for orchestration, `claude-sonnet-5` for bulk jobs
- Frontend: React + Vite, MapLibre/deck.gl (map), Cytoscape.js (network graph)
- Language: Bhashini (MeitY) for Kannada ASR/TTS
- PDF: WeasyPrint

## Layout

Backend and frontend are separate top-level folders, each with its own Dockerfile.
`docker compose` runs db + backend + frontend together.

```
db/init/              *.sql executed in filename order on first boot
  00_extensions.sql   postgis, pgvector, pg_trgm, fuzzystrmatch + schemas
  01_ksp_schema.sql   the KSP source schema (schema: ksp)
  02_derived.sql      everything we compute (schema: derived)

backend/
  app/
    main.py           FastAPI entrypoint
    config.py         settings from env
    db.py             engine + session
    api/              routes, orchestration loop (P14)
    tools/            the tool catalog (P9-P13)
    alerts/           scheduled alert engine (P17a)
    models/           SQLAlchemy models
  ingest/
    synth/            synthetic generator + ground truth (P2)
    loader.py         CSV/Excel ingest + CrimeNo parsing (P3)
    translate.py      BriefFacts -> brief_facts_en (P4)
    socioeconomic.py  Census/district indicators (P4a)
  er/                 entity resolution — the core engine (P5-P8)
  ml/
    mo/               MO clustering (P15)
    risk/             undetected-case + offender risk (P16, P17)
    forecast/         hotspot forecasting (P18)
  tests/

frontend/
  src/                React + Vite + TS (P19-P21)
```

**Two Postgres schemas, deliberately separated:**
- `ksp` — the supplied source schema. Read-only. Never add our columns here.
- `derived` — everything we compute. Safe to drop and rebuild.

Translated text lives in `derived.case_translation.brief_facts_en`, *not* in
`ksp.case_master` — the source stays untouched.

## Commands

```
make up       start everything      make test    backend test suite
make down     stop                  make lint    ruff + tsc
make reset    wipe db, re-init      make psql    psql shell
make tables   list both schemas     make logs    tail all services
```

---

## Schema gotchas (real defects in the supplied ER diagram)

- `ActSectionAssociation.ActID` is INT but `Act.ActCode` is VARCHAR — same for
  `SectionID`/`Section.SectionCode`. `CrimeHeadActSection.ActCode` is correctly VARCHAR.
  We standardize on **VARCHAR**.
- `Inv_OccuranceTime` and `inv_arrestsurrenderaccused` are referenced in the relationship
  matrix but **never defined**. We model them from inference; flag any assumption in comments.
- `ArrestSurrender` has both a direct `AccusedMasterID` FK **and** the junction table. We
  treat the junction as authoritative.
- `Section` has no declared primary key. We add `(ActCode, SectionCode)`.
- `latitude`/`longitude` will be heavily null. Always fall back to `Unit → District` centroid
  and **mark points as precise vs. inferred** in any output.

## Data facts that constrain features

- **Caste, religion, occupation exist only on `ComplainantDetails`** — not on `Accused` or
  `Victim`. Demographic profiling of offenders is impossible and we do not attempt it. We do
  sociology of *victimization* only.
- **No financial, property, phone, or vehicle data exists.** PS1 §7 is a stubbed integration
  point, not an implemented feature. Never fabricate this data.
- **No modus operandi field exists.** MO is derived from `BriefFacts` free text.
- `CrimeNo` format: `1 digit category + 4 district + 4 station + 4 year + 5 serial`.
  Category `1`=FIR, `3`=UDR, `4`=PAR, `8`=Zero FIR.
- `ChargesheetDetails.cstype`: `A`=chargesheet, `B`=false case, `C`=undetected. This is our
  only supervised label — treat it as precious.

---

## Conventions

- `BriefFacts` stays untouched; translated text goes in `BriefFacts_en`. All analysis and
  debugging happens on the `_en` column (the team does not read Kannada).
- Kannada user-facing output is **template-based only**, never free-form generation — the
  templates get validated once by a native speaker. See `web/src/i18n/kn.ts`.
- Entity resolution merges: ≥0.85 auto-merge, 0.60–0.85 goes to the human review queue,
  never auto-merged. Always persist the merge evidence.
- Write tests for the ER scorer and every tool. Skip tests for UI polish.
