# CONSISTENCY — Shared Build Log

**Two developers, two Claude Code sessions, one codebase.** This file is how the other person
(and their Claude Code) finds out what you did.

---

## Rules

**Every Claude Code session:**
1. **Read this file first.** It overrides stale assumptions in `PLAN.md` and `PROMPTS.md` —
   those describe the plan, this describes reality.
2. **Claim before you build.** Add your name to the Claim Board below and commit that change
   *before* writing code. Two people silently building P12 is the expensive failure here.
3. **Log before you stop.** Append a session entry. If you discovered something surprising
   about the data or made a decision that deviates from the plan, that goes in the relevant
   section too — not just the session log.

**Git:** commit `CONSISTENCY.md` on its own, separately from code. It makes conflicts trivial
and keeps the log readable in history. If you both edit it and hit a conflict, **keep both
sides** — this is an append-only log, nothing here should ever be deleted.

---

## Claim Board

Who is working on what, right now. Clear your row when you finish or stop.

| Prompt | Who | Branch | Started | Notes |
|---|---|---|---|---|
| P5 | Claude (Thiru) | claude/repo-consistency-review-l93twi | 2026-07-18 | name parsing + normalization + phonetic key |

---

## Prompt Status

`⬜ not started` · `🟡 in progress` · `✅ done` · `⚠️ done but needs revisit` · `⏭️ skipped`

### Phase 0 — Foundation
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P1 | Repo scaffold + database | ✅ | Thiru | verified: schema loads clean, 29 ksp / 4 derived, 8/8 tests pass |
| P2 | Synthetic data generator ★ | ✅ | Claude | `python -m ingest.synth --cases N`; ground truth → gitignored json |
| P3 | Ingest + CrimeNo parsing | ⬜ | | |
| P4 | Translation layer | ⬜ | | |
| P4a | External socio-economic data | ⬜ | | closes PS1 §4 |

### Phase 1 — Entity resolution
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P5 | Name parsing + normalization ★ | 🟡 | Claude | in progress |
| P6 | Blocking + pairwise scoring | ⬜ | | |
| P7 | Collective resolution ★ | ⬜ | | |
| P7a | Victim-offender overlap | ⬜ | | closes PS1 §2 |
| P8 | ER evaluation harness | ⬜ | | **the F1 number for the slide** |

### Phase 2 — Tool layer and chat
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P9 | Tool framework ★ | ⬜ | | |
| P9a | Data protection posture | ⬜ | | closes PS1 §10 |
| P10 | Retrieval tools | ⬜ | | |
| P10a | Case summary tool | ⬜ | | closes PS1 §6 |
| P11 | Compliance tools | ⬜ | | chargesheet board — high value |
| P12 | Network tools | ⬜ | | |
| P13 | Trend + hotspot tools | ⬜ | | |
| P13a | Event calendar + anomaly detection | ⬜ | | closes PS1 §3 |
| P14 | Orchestration loop ★ | ⬜ | | |

### Phase 3 — Intelligence
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P15 | MO fingerprinting ★ | ⬜ | | |
| P16 | Undetected-case risk model | ⬜ | | |
| P17 | Offender risk + leads | ⬜ | | |
| P17a | Proactive alert engine ★ | ⬜ | | closes PS1 §8 — **above P18** |
| P18 | Hotspot forecasting | ⬜ | | |

### Phase 4 — Interface
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P19 | Frontend shell ★ | ⬜ | | |
| P19a | SCRB strategic dashboard | ⬜ | | policymaker persona |
| P19b | Reasoning path visualization | ⬜ | | closes PS1 §9 |
| P20 | Map + network panes | ⬜ | | |
| P21 | ER review queue | ⬜ | | |

### Phase 5 — Language and export
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P22 | Kannada template system | ⬜ | | |
| P23 | Voice (Bhashini) | ⬜ | | |
| P24 | PDF export | ⬜ | | |

### Phase 6
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P25 | Demo preparation | ⬜ | | |

---

## Decisions that deviate from PLAN.md

When reality forces a change of approach, record it here. `PLAN.md` stays as written; this is
the amendment log. Include *why*, so the other person doesn't undo it.

| Date | Decision | Why | By |
|---|---|---|---|
| 2026-07-18 | Two Postgres schemas: `ksp` (source, read-only) and `derived` (computed) | Keeps the supplied schema pristine and makes all derived work droppable/rebuildable. `brief_facts_en` lives in `derived.case_translation`, never in `ksp.case_master`. | Thiru |
| 2026-07-18 | snake_case table/column names, original PascalCase recorded in SQL `COMMENT` | Postgres folds unquoted identifiers to lowercase anyway, so `CaseMaster` → `casemaster` regardless. Comments keep the mapping to the source diagram explicit. | Thiru |
| 2026-07-18 | `ArrestSurrender.accused_master_id` kept but marked deprecated; junction table authoritative | The diagram has both. One arrest event can cover multiple accused, so the junction is the only structure that can represent reality. **Revisit if organisers say otherwise.** | Thiru |
| 2026-07-18 | Added `gender_master` (INFERRED-3) | `GenderID` is referenced as a "lookup value" by four tables but no lookup table is defined. Seeded M/F/T per the diagram's own description. | Thiru |

---

## Data surprises

Things the real dataset does that the ER diagram didn't warn us about. **This section is the
most valuable one in the file** — put anything here that would waste the other person an hour.

| Date | Finding | Impact | By |
|---|---|---|---|
| 2026-07-18 | **These are SYNTHETIC-data characteristics (P2), not real-data findings.** They stand in until the real dataset lands, and they are what the generator deliberately produces so downstream code has realistic signal to handle. | ER/tools should be built against these shapes | Claude |
| 2026-07-18 | `latitude`/`longitude` ~58% null. Non-null points are district-centroid + jitter. | P13 hotspot code MUST implement the centroid fallback + precise/inferred flag from day one. | Claude |
| 2026-07-18 | `accused_name` formats: honorifics (Sri/Smt/Mr/Kum), `@` aliases, patronymic present ~55% of the time, terminal-vowel drift (Chandru/Chandruu/Chandrua/Chandruappa), transliteration noise (sh↔s, th↔t, doubled letters). One true person can look like 40+ distinct strings. | This is exactly what P5 name parsing + P6 scoring must see through. Don't assume a clean given/patronymic split. | Claude |
| 2026-07-18 | `BriefFacts` language mix ≈ 45% English / 30% transliterated Kannada / 25% Kannada script. Each MO template keeps signature words stable across all three renderings. | P4 translation + P15 MO clustering both rely on this. `mo_by_case` in the ground-truth file is the P15 answer key. | Claude |
| 2026-07-18 | `cstype` class balance on closed cases ≈ A 36% / B 10% / C 54%. ~23% of all cases are still OPEN (no chargesheet_details row) — those are the P16 prediction targets. | P16 has a usable but imbalanced label; ~11.6k open cases at 50k scale. | Claude |
| 2026-07-18 | Age drifts ±2y per appearance around the person's true birth year — the ±2y tolerance in PLAN.md §2 stage 4 is calibrated to exactly this. | P6 age-consistency gate should use ±2y (a tighter gate will drop true matches). | Claude |
| 2026-07-18 | Co-arrest junction: one `arrest_surrender` event covers up to 4 accused; gangs (300 at 50k scale) recur across cases. Zero-FIR (cat 8) ≈ 4%, UDR (cat 3) present. | P7 collective boost and P12 community detection have real edges; P13 zero-FIR flow tool has data. | Claude |

---

## Blockers and open questions

| Raised | Item | Waiting on | Status |
|---|---|---|---|
| | Organizer questions from `PLAN.md` §11 (7 items) | KSP / organizers | ⬜ not sent |
| | Kannada validator for the ~40 templates in P22 | need one native speaker, ~2 hrs | ⬜ not found |

---

## Session log

Newest at the bottom. Append, never edit someone else's entry.

**Format:**

```
### YYYY-MM-DD · <name> · <prompts touched>
Did:      what actually got built
Works:    what you verified running, and how
Broken:   what's failing or half-done
Next:     what the other person should pick up
```

**Example:**

```
### 2026-07-19 · <name> · P5, P6
Did:      Name parser handles S/o, D/o, W/o and @ aliases. Phonetic keys with the
          Dravidian rule set. Blocking on phonetic key + district.
Works:    `pytest tests/er/` — 34 passing. Parsed 50k synthetic names, 96% got a
          clean given-name split.
Broken:   Compound patronymics ("S/o Late Krishnappa") drop the "Late" but sometimes
          eat the name too. ~2% of rows. Left a TODO in er/names.py:118.
Next:     P7 is unblocked. Don't touch er/names.py until I fix the compound case —
          I'll do it tomorrow morning.
```

---

<!-- APPEND NEW ENTRIES BELOW THIS LINE -->

### 2026-07-18 · Claude (Thiru) · P1 verify, P2 claim
```
Did:      Verified P1 for real. No docker daemon in this environment, so brought
          up the host's Postgres 16 cluster directly, installed postgis + pgvector
          via apt, created the ksp role/db, and loaded all three db/init/*.sql in
          order under ON_ERROR_STOP=1. Loads clean. 29 ksp + 4 derived tables,
          exactly as designed. Ran the pytest suite: 8/8 green.

          Fixed one real defect: test_cs_type_constrained_to_known_outcomes did a
          deliberately-failing INSERT on a module-scoped connection and never rolled
          back, so the aborted transaction cascaded two FALSE failures into the next
          two tests. Added conn.rollback() after the expected failure. The schema
          itself was never wrong — all assertions pass on a clean connection.

Works:    `pytest tests/` → 8 passed. DDL applies with zero errors. postgis +
          vector + pg_trgm + fuzzystrmatch all present. party_role enum =
          {accused, victim, complainant}. Section has a PK. act_section_association
          codes are VARCHAR. P1 is now genuinely ✅.

Broken:   Nothing in P1. Note the verification path was host Postgres, not
          `docker compose` — the daemon isn't available here. DDL is identical, so
          this validates the schema; it does not validate the compose wiring itself.

Next:     Building P2 (synthetic generator) next — claimed on the board.
```

### 2026-07-18 · Claude (Thiru) · P2
```
Did:      Built the synthetic FIR generator under ingest/synth/. Real Karnataka
          geography (31 districts + centroids), police org, and a legal framework
          covering exactly the acts/sections the crime catalogue invokes. 11 crime
          types, each with gravity, section mapping, a realistic cstype distribution,
          and MO-signature BriefFacts written in English / transliterated Kannada /
          Kannada script. Hidden ground-truth registry: gangs, repeat offenders, and
          victim-offender duals, with every party row traced back to a true person.
          COPY-based loader. CLI: `python -m ingest.synth --cases N`.

Works:    `python -m ingest.synth --cases 50000` — generates in ~6s, loads in ~10s.
          Verified on the loaded 50k: 0 date-ordering violations, 0 CrimeNo integrity
          violations (incl. district segment == station's district), lat/long 58% null,
          cstype A/B/C = 36/10/54%, 11.6k open cases, 1,697 chargesheet-deadline-band
          cases, co-arrest events up to 4 accused, 0 FK orphans. `pytest` → 17 passed
          (9 new generator invariant tests, no DB needed). ruff clean.

          Concrete proof it works: true person #126 "Chandru Marappa" surfaces 43x as
          Chandruu / Chhandru / Chandrua / Chandruanna / Chandruappa / Mr Chandru S/o
          Maranna ... age wandering 49-57. That is the ER problem, made measurable.

Broken:   Nothing. Two notes for whoever does ER:
          - The generator is separable from the DB (build() returns row tuples), so you
            can unit-test against it without Postgres.
          - The single-person appearance tail is heavy for gang members (some 40+). If
            that skews your F1, cap gang recurrence via RegistryConfig — don't edit the
            per-appearance corruption, it's calibrated to PLAN.md §2.

Next:     P3 (ingest/loader.py + CrimeNo parser + quality report) can run against this
          data now. P5 (name parsing) is the ★ gate for ER and is unblocked — the name
          corruption in names.py is exactly what it has to reverse. P9 (tool framework)
          is independent and parallelizable. See the Data surprises table for the shapes
          to build against. Ground truth is at backend/ingest/synth/ground_truth.json
          (gitignored) — the ER pipeline must NEVER read it; only P8 evaluation may.
```

### 2026-07-18 · Thiru · P1
```
Did:      Full scaffold. backend/ + frontend/ as separate Docker services,
          docker-compose with healthcheck-gated startup, Makefile.
          db/init/*.sql: 29 ksp tables + 4 derived tables. Every deviation
          from the ER diagram marked [FIX-n] / [INFERRED-n] inline — nothing
          changed silently. 8 acceptance tests in backend/tests/test_schema.py.
          Directory tree laid out for all 33 prompts.

Works:    Nothing verified at runtime. Python files compile; SQL parens
          balance; table counts correct (29 ksp / 4 derived).

Broken:   NOT RUN. The postgis image pull was still going when we stopped —
          no container has ever started, the schema has never been loaded, and
          the tests have never executed. Treat P1 as unfinished until someone
          runs `make up && make test` and sees it pass. Expect at least one
          typo in 425 lines of untested DDL.

Next:     Whoever picks this up: run `make reset` first, fix whatever the DDL
          gets wrong, then flip P1 to ✅ in the status table above. Only then
          start P2.

          Open question that blocks P7 later: inv_arrest_surrender_accused is
          INFERRED — its real column structure is unknown and collective
          entity resolution depends on it. Chase the organisers.
```
