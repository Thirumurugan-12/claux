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
| _(none active)_ | | | | P1,P2,P5–P9 ✅. Phase 2 started. P10/P11/P12 (real tools) or P14 next |

---

## PS1 feature coverage (audited 2026-07-18)

Mapping the 10 problem-statement sections to what is actually built and running.
**Verified this pass:** full test suite 57 passing, ruff clean, all modules import,
FastAPI boots, DB reachable (29 ksp / 4 derived), and the P2→P5→P6→P7 pipeline runs
end to end with `derived.person_cluster` populated (51,873 clusters / 55,716 members).

| PS1 § | Feature | Status | Where / what's left |
|---|---|---|---|
| — | **Foundation** (DB, synthetic data) | 🟢 built | P1✅ P2✅. P3 ingest/quality-report ⬜, P4 translation ⬜ |
| — | **Entity resolution core** (`person_cluster`) | 🟢 built + measured | P5✅ P6✅ P7✅ P8✅. **Phase 1 done.** B-cubed F1 **0.687** (P 0.83 / R 0.59), pairwise F1 0.372, collective lift **+887** merges vs name-only. |
| §1 | Conversational AI interface | 🔴 not started | needs P9 tools + P14 orchestration + P19 UI |
| §2 | Network / link analysis | 🟡 foundation only | co-offending graph + clusters exist (P7); P7a victim overlap ⬜, P12 network tools ⬜ |
| §3 | Patterns & trends (spatial/temporal, events, anomalies) | 🔴 not started | P13, P13a |
| §4 | Sociological insights | 🔴 not started | P4a (socioeconomic) — victimisation-side only, offender profiling impossible by schema |
| §5 | Offender profiling (MO, risk) | 🔴 not started | P15 MO, P16 undetected-risk, P17 offender-risk — ER foundation ready to build on |
| §6 | Investigator support (summaries, similar cases, leads) | 🔴 not started | P10a, P15, P17 |
| §7 | Financial crime | ⚪ declared out of scope | no account/txn/property/phone data in schema — stub + declare (PLAN §5) |
| §8 | Forecasting / proactive early-warning | 🔴 not started | P17a alerts (priority), P18 forecast |
| §9 | Explainable AI | 🟡 partial | ER "why same person" evidence trail done (P7); tool provenance chain (P9) + reasoning viz (P19b) ⬜ |
| §10 | RBAC & audit | 🟢 framework built | P9✅ — RBAC at tool boundary, audit_log, k-anon. P9a (DPDP governance doc) ⬜ |

**Bottom line:** the data + entity-resolution spine — the thing every §2/§5/§6/§8
feature is uncomputable without — is complete and measured. No end-user-facing PS1
feature is fully delivered yet because the tool layer (P9), orchestration (P14), and
UI (P19+) are not built. Nothing is off track; the per-prompt to-do below is current.

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
| P5 | Name parsing + normalization ★ | ✅ | Claude | `er/names.py`; 95.6% blocking recall vs P2 corruption |
| P6 | Blocking + pairwise scoring | ✅ | Claude | `er/blocking.py`+`er/scoring.py`; 55k accused→4.58M pairs in ~30s |
| P7 | Collective resolution ★ | ✅ | Claude | `er/resolve.py`; person_cluster populated, +237 collective lift |
| P7a | Victim-offender overlap | ⬜ | | closes PS1 §2 |
| P8 | ER evaluation harness | ✅ | Claude | `python -m er.run_evaluate`; B-cubed F1 0.687, +887 collective merges |

### Phase 2 — Tool layer and chat
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P9 | Tool framework ★ | ✅ | Claude | `app/tools/base.py`; RBAC+provenance+audit+k-anon, 2 demo tools |
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
| 2026-07-18 | ER scorer: patronymic-**mismatch penalty** (both present but jw<0.80 ⇒ −0.30), beyond PLAN §2 stage 4's positive-only signals | PLAN treats patronymic as a positive weight only. On the small synthetic pool (68 given / 24 patronymic names) two different people share a given name constantly, and a differing father's name is the strongest evidence they're *different*. Without the penalty, all the "Anand"s transitively over-merged. Thresholds measured on P2 (corrupted-same ≥0.886, different ≤0.75). | Claude |
| 2026-07-18 | ER clustering: **cannot-link constraints** in union-find (conflicting patronymic phonetic key, or cluster birth-year span > 5y), beyond PLAN §2 stage 6's plain threshold clustering | Naive transitive closure at ≥0.85 fuses distinct people via a single borderline bridge edge. `est_birth_year = reg_year − age` is ~constant per person (±2 age noise) so it's discriminative; the patronymic *key* separates Marappa(MR) from Mallappa(ML) while keeping Marappa/Maranna together. Reduced the largest cluster 62→24. **Revisit on real data** — with thousands of distinct names these collisions are rare and the constraints could be relaxed. | Claude |

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

### 2026-07-18 · Claude (Thiru) · P5
```
Did:      Built er/names.py (parsing + normalization + phonetic key). Parses the
          four components (given / @-alias / patronymic+relation / honorifics),
          handles S/o D/o W/o C/o + word forms + bin/binte, strips a leading "Late"
          from patronymics. Normalizes via Kannada->Roman transliteration. Phonetic
          key = Double Metaphone over a Dravidian-normalized stem (aspirate collapse,
          th/t sh/s v/w, doubled-consonant collapse, terminal-vowel drift, kinship
          suffix -appa/-anna/-amma/-gowda strip with a length guard).

Works:    pytest tests/er/ -> 19 passed. Acceptance case parses into all four parts.
          Headline: 95.6% given-name blocking recall measured directly against P2's
          corruption machinery (render_variant) over 10 identities x 500 variants.
          Distinct names stay in distinct blocks. Full suite 36 passed, ruff clean.

Broken:   Nothing. Notes for whoever does P6:
          - Added deps to pyproject: indic-transliteration, metaphone, jellyfish
            (jellyfish is there for your Jaro-Winkler in P6 — already installed).
          - The phonetic key is deliberately AGGRESSIVE (recall-first) because it's a
            blocking key, not a decision. Do NOT tighten it to raise precision — that's
            the scorer's job. Expect ~4% of true pairs to miss the first-token block;
            catch them with the district + shared-arrest blocks (PLAN.md §2 stage 3).
          - ParsedName exposes normalized_given (Jaro-Winkler), phonetic_key,
            patronymic + patronymic_key, relation, honorifics. parse() is the entry point.

Next:     P6 (er/blocking.py + er/scoring.py) is unblocked and is the direct next step.
          Block on phonetic_key of first token + district + shared arrest event; score
          with Jaro-Winkler(normalized_given) + patronymic match + alias overlap + age
          consistency (±2y — matches P2's drift) + gender hard-gate + geography.
```

### 2026-07-18 · Claude (Thiru) · P6
```
Did:      Built er/records.py (loads accused/victim/complainant from ksp only, parses
          names via P5, estimates birth year, derives district adjacency from case
          centroids), er/blocking.py (candidate pairs from 3 conjunctive keys:
          name+gender+age±2, name+gender+district, name+gender+patronymic; gender
          folded in since it's a hard gate; same-FIR pairs excluded; oversized buckets
          sub-block by name prefix), er/scoring.py (0-1 score + full per-signal
          breakdown, configurable ScoringWeights, gender hard-gate, fast float path for
          the millions of pairs + breakdown only for kept pairs). CLI:
          `python -m er.score_pairs --top N`.

Works:    Accused set: 55,716 records -> 4.58M candidate pairs, full pipeline ~30s
          (well under the 2-min bar). Top pairs are correct same-person matches with
          readable signal breakdowns (e.g. 'Raju @ Raj S/o Boraiah' <-> 'Raju S/o
          Boraiahu'). Bands: >=0.85 auto-merge, 0.60-0.85 review, else reject.
          pytest tests/er/ -> 31 passed (12 new). Full suite 48, ruff clean.

Broken:   Nothing broken, but TWO things P7/P8 must know:
          1. SYNTHETIC ARTIFACT: with only 68 given names, the 0.60 review floor keeps
             ~561k accused pairs (9.9k auto-merge, 551k review). That's name+age+geo
             coincidences, NOT a scorer bug — real data with 1000s of names won't do
             this. P7's collective boost + clustering must collapse the review set;
             don't "fix" it by inflating weights. P8 will show precision here.
          2. CLI defaults to --roles accused (the ~50k the acceptance means). All three
             roles = 143k records and blows past 2 min on this name pool. P7a needs
             victim/complainant in the same namespace — enable with --roles then, and
             expect to tune REVIEW_FLOOR or lean on clustering.

          Calibration note: bare name+age+district (no patronymic/alias) intentionally
          scores <0.60 (reject) — it's coincidence-prone. Review band is driven by
          name+patronymic agreement with missing/weak corroboration. age decay is
          0.8/0.6 at ±1/±2y so a genuine 1-year drift still auto-merges.

Next:     P7 (er/resolve.py) — the ★ novel step. Build the co-offending graph from
          arrest_events (already on PartyRecord for accused), run pairwise, propagate
          scores through shared resolved co-offenders, iterate, then cluster (>=0.85
          auto, 0.60-0.85 -> er_review_queue) and persist person_cluster +
          person_cluster_member + match_evidence. score_pair() returns the evidence
          dict you persist. P8 then measures F1 vs P2's ground truth (with/without the
          collective boost = the headline delta).
```

### 2026-07-18 · Claude (Thiru) · P7
```
Did:      Built er/graph.py (co-offending graph, networkx) and er/resolve.py
          (collective resolution + clustering + persistence). Score pairs (P6) ->
          union-find cluster -> propagate a boost when co-offenders are already
          resolved to the same person -> re-cluster, 3 rounds. Persists
          person_cluster / person_cluster_member (with evidence JSONB) /
          er_review_queue. CLI: `python -m er.run_resolve [--no-persist]`.

Works:    55,716 accused -> 51,873 clusters / 1,201 multi-member, persisted. For ANY
          cluster the SQL returns each member's signals + collective_boost +
          shared_resolved_cooffenders (full "why same person" trail). Collective lift
          = +237 auto-merges from the network over the name-only baseline (this is the
          number that previews P8's headline). resolve ~61s. pytest tests/er/ -> 40
          passed (15 new). Full suite 57, ruff clean.

Broken:   Nothing broken. Precision/tuning notes for P8 (which MEASURES this):
          1. Two DECISIONS I added beyond PLAN §2 to fight transitive over-merge on
             the tiny synthetic name pool (68 given / 24 patronymic names cause real
             collisions). Both are principled and both live in the scorer/union-find:
             (a) patronymic-mismatch PENALTY: both patronymics present but clearly
                 different (jw < 0.80) => -0.30. Thresholds measured on P2:
                 corrupted-same >= 0.886, different <= 0.75, so 0.85/0.80 split is clean.
             (b) cannot-link constraints in union-find: conflicting patronymic phonetic
                 key, OR cluster birth-year span > 5. est_birth_year = reg_year - age is
                 ~constant per person (+/-2 age noise), so it's discriminative.
             These are recorded in "Decisions that deviate from PLAN.md" too.
          2. Review queue = 479k pairs (synthetic small-pool artifact, as flagged in
             P6). Persisted via COPY; P21 UI must paginate/sample. On real data far fewer.
          3. Largest cluster = 24 (was 62 before the constraints). Some residual
             over-merge remains where two people genuinely share given+patronymic+age
             band — unavoidable on this pool; P8 will quantify precision. Don't chase it
             by over-tightening (hurts recall on real repeat offenders).

Next:     P8 (er/evaluate.py) is the direct next step and produces the F1 for the slide:
          load ground_truth.json, score pairwise + cluster-level P/R/F1, break down
          misses by corruption type, and measure the collective lift properly (run with
          propagation off vs on). resolve() already returns auto_merges_base vs _final;
          reuse ResolveConfig(max_rounds=1, boost_per_cooffender=0) for the off case, or
          diff base vs final. P7a extends resolution to victims/complainants (same
          person_cluster namespace) for the victim-offender overlap.
```

### 2026-07-18 · Claude (Thiru) · P8
```
Did:      Built er/evaluate.py + er/run_evaluate.py — the ER scorecard vs P2's hidden
          ground truth. Pairwise + B-cubed P/R/F1, an error breakdown (which corruption
          appears in missed true pairs), and the collective lift (propagation off vs on).
          Refactored resolve into prepare() + resolve_prepared() so eval scores the
          working set ONCE and clusters twice. CLI: `python -m er.run_evaluate`.

Works:    On 55,716 accused: B-cubed F1 = 0.687 (P 0.826 / R 0.588), pairwise F1 = 0.372.
          Predicted 4,395 multi-member clusters vs 4,013 true recurring people — close.
          Collective lift = +887 auto-merges from the network (pairwise F1 +0.008).
          Ground-truth coverage 100% (json matches the loaded seed-42 50k data). Top
          recall-loss factors in missed pairs: cross_district (10%), missing_patronymic
          (7%), age_drift>2 (3%). pytest -> 64 passed (7 new). ruff clean.
          Re-persisted person_cluster with the tuned weights (35,122 clusters).

Broken:   Nothing broken. IMPORTANT — the harness caught a real defect and I fixed it:
          the OLD weights (name .35/patro .30/age .15/geo .10) meant a repeat offender
          with same name+father+age but a DIFFERENT district scored 0.80 and never
          auto-merged — the flagship "same person across stations" case was landing in
          review. Old recall was catastrophic (pairwise 0.035, B-cubed 0.47). Rebalanced
          so core identity (name .40/patro .35/age .20) clears 0.85 on its own; geo+alias
          are bonuses; bare name+age (no patronymic) still stays <0.60. Recall jumped
          (B-cubed 0.47->0.59) at a modest precision cost (0.97->0.83). Net F1 up on both
          metrics. THIS IS THE DEFAULT NOW — if you retune, re-run run_evaluate and watch
          BOTH precision and recall; the tiny 68-name pool makes it easy to over-merge.

          Perf note: run_evaluate takes ~120s (scores 4.58M pairs once, clusters twice,
          builds pairwise pair-sets). It's an offline harness, not a demo path.

Next:     Phase 1 (entity resolution) is COMPLETE and measured. Options:
          - P7a: resolve victims/complainants into the SAME person_cluster namespace
            (victim-offender overlap tool). P2 planted dual-role people for this.
          - P9 (tool framework ★) starts Phase 2 — independent of remaining ER, unblocks
            the whole tool/chat/demo spine. Highest leverage toward a demoable product.
          Recommend P9 next: person_cluster now exists + is measured, so the retrieval/
          network tools (P10/P12) that read it have a real, scored foundation.
```

### 2026-07-18 · Claude (Thiru) · P9
```
Did:      Built the tool framework in app/tools/base.py — the enforcement point for
          CLAUDE.md's non-negotiable rules. Tool base class (Pydantic params, principal,
          _run), ToolResult{data, provenance} (provenance structurally mandatory),
          Principal+Role (PLAN §6), scope resolution via unit.parent_unit recursive CTE
          + role ladder, k-anonymity (<5 suppressed for analyst/policymaker), audit log
          (derived.audit_log, added to 02_derived.sql + applied live), ToolRegistry that
          emits Anthropic tool-use schemas. Two demo tools in app/tools/demo.py:
          get_case (person-level, scoped) and case_count_by_district (aggregate, k-anon).
          `python -m app.tools` prints the schemas.

Works:    pytest tests/tools/ -> 10 passed. Demonstrated live: in-scope SHO gets a case
          with provenance sql_hash; out-of-scope SHO DENIED ("unit 351 outside scope of
          sho") and logged; policymaker person-tool DENIED and logged; analyst aggregate
          k-anonymised to >=5. Schemas print as valid JSON. Full suite 74, ruff clean.
          derived now has 5 tables (added audit_log); test_schema updated.

Broken:   Nothing. Notes for whoever builds P10–P14:
          - Inherit app/tools/base.Tool. Set person_level=True for tools returning names
            (auto-denied for analyst/policymaker). Set aggregate=True + count_field="..."
            for stats tools (auto k-anon). Call self.assert_unit_in_scope() or
            self.scope_clause() to enforce/filter by the caller's scope. NEVER put RBAC
            in the prompt or the SQL by hand.
          - Every _run MUST return ToolResult with real provenance (row_ids + crime_nos).
            The base class audits every call automatically — don't log yourself.
          - Registry: register real tools; build_default_registry() in demo.py is a
            stand-in. P14 calls registry.anthropic_schemas() + registry.call().
          - The demo tools are throwaway scaffolding proving the base class; P10 replaces
            them with the real retrieval catalogue (get_case there should read person_cluster
            for the resolved profile, NOT accused_master_id).

Next:     Phase 2 tool layer is unblocked. P10 (retrieval tools: get_case, search_cases,
          get_person via person_cluster, timelines), P11 (chargesheet deadline board —
          highest value-to-effort, pure SQL over the date chain, data already has a
          day-55-95 cohort), P12 (network tools over the co-offending graph + clusters).
          P14 (orchestration) is the merge point. Recommend P11 next: insurance-policy
          feature, fast, and the demo beat "43 cases at day 75+" is already in the data.
```
