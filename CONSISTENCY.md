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
| P1 | Thiru | main | 2026-07-18 | scaffold + DDL — in progress |

---

## Prompt Status

`⬜ not started` · `🟡 in progress` · `✅ done` · `⚠️ done but needs revisit` · `⏭️ skipped`

### Phase 0 — Foundation
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P1 | Repo scaffold + database | ⚠️ | Thiru | **built, NOT verified** — containers never run |
| P2 | Synthetic data generator ★ | ⬜ | | |
| P3 | Ingest + CrimeNo parsing | ⬜ | | |
| P4 | Translation layer | ⬜ | | |
| P4a | External socio-economic data | ⬜ | | closes PS1 §4 |

### Phase 1 — Entity resolution
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P5 | Name parsing + normalization ★ | ⬜ | | |
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
| | | | |

Expect entries here about: `latitude`/`longitude` null rate, `AccusedName` formats nobody
documented, the two undefined tables, `BriefFacts` language mix, `cstype` class balance.

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
