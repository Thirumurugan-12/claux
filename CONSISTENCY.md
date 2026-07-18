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
| P1 | Repo scaffold + database | ⬜ | | |
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
| | | | |

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
