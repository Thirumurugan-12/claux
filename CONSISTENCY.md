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
| _(none active)_ | | | | P1,P2,P5–P15,P19 ✅ + Catalyst pivot ✅ + UI/UX redesign ✅ + bespoke revision & FE refactor ✅ + bento-grid UI upgrade ✅. 21 tools + chat UI. Next (demo path): P16→P17→P17a→P20→P25. |

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
| §1 | Conversational AI interface | 🟢 built | P14 orchestration + **P19 UI ✅** — streaming chat, role switcher (RBAC demo), evidence drawer, network/map panes that update from the answer. P20 upgrades panes to MapLibre/Cytoscape. |
| §2 | Network / link analysis | 🟢 built | **P12 ✅** — person_network / shortest_path / communities (Louvain, cross-jurisdiction flag) / repeat_offenders over the resolved-person graph. P7a victim overlap ⬜ (extends to victims). |
| §3 | Patterns & trends (spatial/temporal, events, anomalies) | 🟢 built | **P13 ✅** — crime_trend, hotspot_scan (DBSCAN + precise/centroid honesty), spatiotemporal_clusters, compare_to_baseline (red-zone z-score), seasonality, zero_fir_flows. P13a (event calendar + anomaly) ⬜. |
| §4 | Sociological insights | 🔴 not started | P4a (socioeconomic) — victimisation-side only, offender profiling impossible by schema |
| §5 | Offender profiling (MO, risk) | 🟡 MO built | **P15 ✅** — MO fingerprinting (109 clusters, homogeneity 1.000 / V-measure 0.681 vs hidden GT), get_mo_cluster + find_similar_cases w/ outcomes. P16 undetected-risk, P17 offender-risk ⬜. |
| §6 | Investigator support (summaries, similar cases, leads) | 🟡 partial | P10✅ (get_case/person/timeline/chargesheet). P10a case-summary, P15 similar-cases, P17 leads ⬜ |
| §7 | Financial crime | ⚪ declared out of scope | no account/txn/property/phone data in schema — stub + declare (PLAN §5) |
| §8 | Forecasting / proactive early-warning | 🔴 not started | P17a alerts (priority), P18 forecast |
| §9 | Explainable AI | 🟡 partial | ER "why same person" evidence trail (P7); provenance chain surfaced in the chat answer (P14) AND the evidence pane with clickable CrimeNos → source FIR (P19 ✅); reasoning-path *node diagram* (P19b) ⬜ |
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
| P10 | Retrieval tools | ✅ | Claude | `app/tools/retrieval.py`; get_person reads person_cluster (resolved profiles) |
| P10a | Case summary tool | ⬜ | | closes PS1 §6 |
| P11 | Compliance tools | ✅ | Claude | `app/tools/compliance.py`; deadline board (148 heinous day-75+) + reg-delay |
| P12 | Network tools | ✅ | Claude | `app/tools/network.py`; person-level co-offending graph, 4 tools, Cytoscape-ready, cross-jurisdiction detection |
| P13 | Trend + hotspot tools | ✅ | Claude | `app/tools/trends.py`; 6 tools, DBSCAN hotspots w/ precise-vs-centroid honesty, red-zone z-score, CrimeNo category-digit zero-FIR |
| P13a | Event calendar + anomaly detection | ⬜ | | closes PS1 §3 |
| P14 | Orchestration loop ★ | ✅ | Claude | `app/api/`; POST /chat + tool-calling loop over catalog, 28/28 eval, injectable LLM client |

### Phase 3 — Intelligence
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P15 | MO fingerprinting ★ | ✅ | Claude | `ml/mo/` + `app/tools/mo.py`; TF-IDF→SVD→HDBSCAN, pgvector, V-measure 0.681 (homogeneity 1.0) |
| P16 | Undetected-case risk model | ⬜ | | |
| P17 | Offender risk + leads | ⬜ | | |
| P17a | Proactive alert engine ★ | ⬜ | | closes PS1 §8 — **above P18** |
| P18 | Hotspot forecasting | ⬜ | | |

### Phase 4 — Interface
| | Prompt | Status | By | Notes |
|---|---|---|---|---|
| P19 | Frontend shell ★ | ✅ | Claude | `frontend/`; dark 3-pane shell, streaming chat, RBAC role switcher, evidence drawer + clickable CrimeNos, SVG network/map panes. `npm run build` clean |
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
| 2026-07-19 | **Hosting pivots to Zoho Catalyst** (hackathon platform partner): AppSail (backend), Slate (frontend), Job Scheduling (P17a), SmartBrowz (P24 PDF), Stratus (exports). See `DEPLOYMENT-CATALYST.md`. | Partner requirement — maximize Catalyst usage. PLAN.md's generic docker-compose hosting stays as the local dev path; compose is unchanged for `make up`. | Claude |
| 2026-07-19 | **Postgres stays EXTERNAL to Catalyst** — not migrated to Catalyst Data Store | Verified against Catalyst's own agent-skills docs: Data Store/ZCQL has no recursive CTEs (RBAC unit-subtree scope), no PostGIS (geo), no pgvector (semantic search), no pg_trgm (fuzzy match). The ER core is unimplementable on it. Everything above the DB is Catalyst. | Claude |
| 2026-07-19 | **LLM = Catalyst QuickML LLM Serving** (Qwen 2.5, BYOK) via `OpenAICompatClient`; direct Anthropic (`claude-opus-4-8`) demoted to local-comparison fallback (`LLM_PROVIDER=anthropic`) | Catalyst is the ONLY permitted cloud, so the LLM must be Catalyst's own. QuickML LLM Serving is the concrete native offering (Qwen models, POST endpoint + Zoho OAuth). "UniAI" turned out not to be a findable Catalyst component; kept the `UNIAI_*` env-var names as the generic "Catalyst LLM endpoint" config to avoid churn. Wire format assumed OpenAI-compatible (undocumented; verify with `run_eval --live`), with `UNIAI_CHAT_PATH`/`UNIAI_AUTH_SCHEME` knobs. | Claude |
| 2026-07-19 | **Tool calling defaults to `prompted` mode**, not native OpenAI `tools` | Whether QuickML's serving endpoint exposes OpenAI function-calling is undocumented and can't be assumed — the entire loop depends on tool selection. `prompted` injects the tool catalogue + a strict JSON protocol (`{"tool":...}` / `{"final":...}`) into the system prompt and parses the reply, so the loop runs on ANY chat model incl. a plain Qwen deployment. `UNIAI_TOOL_MODE=native` is available when the endpoint supports tools (better quality). | Claude |
| 2026-07-19 | **Frontend gained a light mode + moved off the all-monospace look** (PLAN.md/P19 describe "dark/dense/operational", implicitly mono-first) | The redesign keeps dark as the DEFAULT and stays dense/operational, but adds a sandalwood/ivory light theme (toggle in top bar, persisted to `localStorage` under `ksp-theme`, no-flash init script in `index.html`) for daylight/projector demos and accessibility. Body/UI type is now Inter, headings Outfit, with **JetBrains Mono reserved for data/IDs/CrimeNos only** — the previous all-mono body hurt readability of prose answers. Noto Sans Kannada is in the body stack so the Kannada voice/text output renders. Palette is Karnataka-rooted (Mysore gold primary, Hampi terracotta for heat/danger, Kaveri teal for info/links). No backend, API, prop, or data-contract change. | Claude (Opus) |

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
| 2026-07-19 | **Zero FIRs (cat 8) do NOT model origin≠destination in the synthetic data.** P2 flips the CrimeNo category digit to 8 for ~4% of FIRs but registers them under the SAME district/station as everything else — coords, crime_no, and police_station_id all agree. Verified: 0 of 1,902 zero FIRs have a CrimeNo-embedded district differing from the assigned unit. | `zero_fir_flows` (P13) therefore returns 0 cross-jurisdiction transfers on synthetic data — this is correct, not a bug. The tool computes flow from the real CrimeNo-vs-assigned-unit divergence, so it lights up on real KSP data; it does NOT fabricate a destination. If a richer zero-FIR demo is wanted, P2 must be extended to set a distinct actual-jurisdiction unit (schema-compatible: make crime_no's station differ from police_station_id) — but that needs a re-resolve. Don't "fix" the tool to invent flows. | Claude |
| 2026-07-19 | hotspot geo: only ~42% of cases carry coordinates (58% null, as flagged). The non-null ones are district-centroid+jitter, not survey-grade. | `hotspot_scan` (P13) clusters precise-coord cases ONLY and reports the excluded centroid-only count openly (coverage block + caveat). Never cluster the null-coord rows at their centroid — 28,970 identical centroid points would create giant fake hotspots. | Claude |

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

### 2026-07-19 · Claude (Thiru) · P15
```
Did:      Built MO fingerprinting (ml/mo/) — the modus-operandi layer the schema lacks.
          Pipeline: brief_facts (Kannada-script romanised via indic-transliteration) →
          TF-IDF → TruncatedSVD 128-d (L2-normalised, stored in pgvector) → HDBSCAN on a
          24-d top-variance view (fast; 128-d neighbour search was the bottleneck) →
          deterministic top-terms label (LLM labeller pluggable). Persists derived.
          mo_cluster + derived.case_mo_assignment (vector(128), hnsw cosine index; added
          to 02_derived.sql + applied live). Tools app/tools/mo.py: get_mo_cluster,
          find_similar_cases (cosine kNN via <=>, each result WITH cstype outcome +
          "N similar, k chargesheeted" summary). CLI: python -m ml.mo.

Works:    Full 50k: 109 clusters, 4.9% noise, V-measure 0.681 (homogeneity 1.000 /
          completeness 0.517) vs the hidden mo_by_case ground truth. Clusters are
          eyeball-real: OTP/vishing fraud, chain-snatching (English + a separate
          romanised-Kannada cluster), house burglary, dowry harassment. pytest
          tests/tools/test_mo.py -> passed (pipeline on a 3k subsample + both tools).
          Registered (21 tools). run_eval 40/40. Full suite 158 passed, ruff clean.

Broken:   Nothing. Notes:
          - HAD to regenerate ground_truth.json: the on-disk GT predated mo_by_case (0
            entries). Fixed with `python -m ingest.synth --cases 50000 --seed 42 --no-load`
            — regenerates GT deterministically WITHOUT touching the DB/person_cluster.
          - LEXICAL, not neural: a multilingual sentence-transformer (the prompt's first
            choice) needs torch (~GB) the env can't take. TF-IDF works because the
            generator keeps signature slot words as literal Roman tokens across en+translit
            (~75%); homogeneity is 1.000 so clusters are pure, but completeness 0.517
            because the SAME MO in English vs romanised-Kannada lands in separate clusters.
            P4 (BriefFacts_en translation) would lift completeness by unifying the scripts.
          - LLM cluster labelling (claude-sonnet-5, per prompt) is pluggable via
            fit_clusters(labeller=...); default is deterministic top-terms so it runs
            offline. Wire the labeller once the Catalyst LLM key exists.
          - Clustering is an OFFLINE job (~30s at 50k); not a request path. Re-run
            `python -m ml.mo` after any data reload.

Next:     P16 (undetected-case risk) — cstype C is the label, MO cluster + the compliance/
          timeline features are predictors. Then P17 (offender risk + leads) uses MO +
          ER + P16. sklearn ready.
```

### 2026-07-19 · Claude (Thiru) · P19 (+ small backend support)
```
Did:      Built the frontend shell in frontend/ (React+Vite+TS, dark/dense/operational).
          - Two-column workspace: streaming chat (left) + a tabbed pane (Evidence /
            Network / Map) on the right. Asking a question repaints the panes — the
            "one product" linkage the prompt asks for.
          - Streaming chat consumes /chat/stream SSE; tool-call chips appear inline as
            the loop runs; text-only history kept for multi-turn.
          - Role switcher (SHO/DySP/SP/SCRB Analyst/Policymaker) drives RBAC live:
            switching role remounts the chat with a new principal, so the SAME question
            returns different scope. IDs come from a new GET /demo/principals (real
            unit/district ids from the data).
          - Evidence pane = provenance chain; every CrimeNo is a chip that opens the FIR
            via POST /case (get_case + RBAC), incl. honest 403 when out of jurisdiction.
          - Network pane: lightweight SVG radial graph from get_person_network /
            find_shortest_path / detect_communities result data. Map pane: SVG hotspot
            scatter over a Karnataka bbox from hotspot_scan, showing the precise-vs-
            centroid coverage openly. P20 upgrades these to Cytoscape / MapLibre+deck.gl.
          Backend support (small): ToolCallRecord/stream now carry the tool result `data`
          so panes render without re-running tools; GET /demo/principals; POST /case.

Works:    `npm run build` (tsc -b && vite build) clean — 33 modules, 157kB. Live-curled
          /demo/principals (all 5 roles w/ real ids + readable scope) and /case (returns
          the FIR). Backend suite 152 passed (3 new route tests: principals, case ok,
          case out-of-scope 403), ruff clean.

Broken:   Nothing, but the chat itself needs the LLM configured — with UNIAI unset,
          /chat/stream returns 503 and the UI shows a clear banner (by design). To demo
          the chat end to end you need the Catalyst QuickML endpoint+key (UNIAI_* ) OR
          LLM_PROVIDER=anthropic. The panes/evidence/role-switch/case-drawer are all
          driven by real backend data and work regardless. Proxy target is now
          VITE_API_TARGET (compose default http://backend:8000; set to the AppSail URL
          for a Slate deploy).

Next:     P20 (MapLibre+deck.gl map with district boundaries + red-zone pulse; Cytoscape
            network with role colouring + click-to-load-into-chat) is the direct upgrade
            of the two placeholder panes — the data contracts (Cytoscape {nodes,edges};
            hotspot lat/lon + coverage) are already what the tools emit.
          P19b (reasoning-path node diagram) reuses P20's Cytoscape.
          P15 (MO fingerprinting) is unblocked — sklearn is installed.
```

### 2026-07-19 · Claude (Thiru) · P13
```
Did:      Built app/tools/trends.py — the 6 trend/hotspot tools (PLAN §3 tools 11–16),
          all aggregate + scoped + explicit k-anon:
          - crime_trend: date_trunc time series (day/week/month/year) + filters.
          - hotspot_scan: DBSCAN (sklearn) over PRECISE coords only; reports the
            precise-vs-centroid split openly and excludes null-coord cases from
            clustering (see geo data-surprise). Added scikit-learn to deps.
          - spatiotemporal_clusters: (district x daypart) hot cells from incident hour.
          - compare_to_baseline: per-district recent-window vs baseline z-score, red-zone
            flag — the proactive-early-warning signal.
          - seasonality: month-of-year + day-of-week distributions with peaks.
          - zero_fir_flows: CrimeNo category-digit (8) extraction; genuine cross-juris
            flow only where CrimeNo district != assigned unit (see zero-FIR surprise).
          Shared helpers: parse_crime_no (18-digit split), cached district_centroids.

Works:    Live on 50k: crime_trend 55 monthly buckets/50000; hotspot_scan 384 hotspots on
          21,030 precise (42.1%), 28,970 centroid-only excluded + caveat; spatiotemporal
          15 cells; compare_to_baseline 13 red zones / 31 districts; seasonality peak
          month 3 / Sat; zero_fir_flows 1,902 zero FIRs, 0 cross-juris (honest). SP scope
          verified (district-1 subset). pytest tests/tools/test_trends.py -> 10 passed.
          Registered (19 tools now). 6 eval questions -> run_eval 38/38. Full suite 149
          passed, ruff clean.

Broken:   Nothing. Two data truths now logged in Data surprises: (1) synthetic zero FIRs
          don't model origin!=destination, so zero_fir_flows shows 0 flows — correct, not
          a bug, real-data-ready. (2) hotspots run on ~42% precise coords only; the rest
          are centroid-only and reported, never clustered.
          - k-anon: applied explicitly in each tool for analyst/policymaker (the base
            class only auto-suppresses when data is a bare list; these return dicts).
          - 384 hotspots at eps=2km/min=5 is a lot (district-centroid+jitter fragments);
            sorted by size so the top ones lead. Tune eps_km/min_samples per query.

Next:     P13a (event calendar + anomaly detection) finishes §3, OR P19 (frontend, Slate)
          to surface the 19 tools + the map/network panes the hotspot/community outputs
          are already shaped for (Cytoscape for P12, lat/lon clusters for P13). sklearn is
          now available for P15 (MO clustering) / P16 (risk) / P18 (forecast).
```

### 2026-07-19 · Claude (Thiru) · P12
```
Did:      Built app/tools/network.py — the 4 network tools (PLAN §3 tools 7–10) over a
          PERSON-level co-offending graph. Nodes = person_cluster_id (resolved accused
          people), edges = co-arrest via ksp.inv_arrest_surrender_accused, weighted by
          shared-event count. Distinct from er/graph.py (which is per-FIR accused rows
          for collective resolution) — this builds ON the resolution it produced.
          - get_person_network: depth-limited ego graph (BFS-capped at max_nodes).
          - find_shortest_path: shortest co-offending chain between two people.
          - detect_communities: Louvain (seed=42), flags groups spanning >1 police
            station (the flagship — cross-jurisdiction gangs invisible to one station).
          - get_repeat_offenders: prolific offenders by linked-FIR count + co-offender
            degree.
          Graph is built once and cached (get_person_graph / reset_person_graph). All
          outputs Cytoscape.js-ready {nodes, edges} for P20. All person_level=True.

Works:    Graph builds in ~1.6s: 35,122 nodes / 13,477 co-offending edges. pytest
          tests/tools/test_network.py -> 13 passed (graph build, real co-offender edge,
          cache reuse, ego graph, out-of-scope + no-record denials, shortest path deg=1,
          community cross-jurisdiction consistency + filter, repeat-offender sort/
          threshold, analyst denial, deterministic build). Registered in catalog (13
          tools now). Added 4 eval questions -> run_eval 32/32 offline. Full suite 139
          passed, ruff clean.

Broken:   Nothing. Notes:
          - RBAC = induced subgraph on people with >=1 FIR in the caller's units (same
            rule as get_person, lifted to the graph). So a single SHO can't see cross-
            jurisdiction; a DySP/SP over a multi-station subtree CAN — that's the intended
            line and what makes the cross-jurisdiction demo work. detect_communities for
            an SP over a whole district returns ~25 groups, all cross-jurisdiction.
          - SYNTHETIC ARTIFACT (unchanged from P7/P8): the tiny name pool leaves some
            over-merged clusters that span many districts (e.g. one seed spanned 18). On
            real data these shrink. Don't tune the graph to hide it — it's an ER-precision
            artifact P8 already quantifies.
          - stations_in_view is intersected with the caller's scope, so a group's
            "stations_spanned" never reveals jurisdictions the caller doesn't own.

Next:     P13 (trend + hotspot tools, §3 still 🔴) is the natural next tool tier — same
          pattern, auto-registers into /chat, and test_every_tool_has_a_question enforces
          an eval question per tool. Or P19 (frontend, Slate) to make the 13 tools +
          network graphs visible. P7a would extend this graph to victims (victim-offender
          overlap) for the rest of §2.
```

### 2026-07-19 · Claude (Thiru) · P14
```
Did:      Built the orchestration loop under app/api/. This is the merge point: the P9
          tool catalogue (catalog.build_registry) is now a conversation.
          - llm.py: an LLMClient boundary. AnthropicClient (claude-opus-4-8, adaptive
            thinking, streaming via .get_final_message) is the production path;
            ScriptedClient replays authored assistant turns for deterministic offline
            tests. The orchestrator NEVER imports the SDK — it holds an LLMClient.
          - orchestrator.py: a MANUAL tool-calling loop (not the SDK tool runner) because
            every call must pass through ToolRegistry.call, where RBAC/provenance/audit
            live. Denials become is_error tool_results the model must relay; refusals
            author no provenance. Loop is an event generator (iter_chat) shared by chat()
            and the SSE route. System prompt encodes CLAUDE.md's two hard rules.
          - routes.py: POST /chat (answer + provenance chain + history for multi-turn) and
            POST /chat/stream (SSE, emits each tool call then the answer). LLM client is a
            FastAPI dependency, overridable in tests.
          - eval_set.py + run_eval.py: 28 questions — one per tool, RBAC denials, and
            unanswerable-must-refuse (financial/vehicle/phone/weather/predict-a-person/
            opinion) — graded on WHICH tool fired + success/denial, not answer wording.
            Plus a 3-turn transcript (resolve person -> drill into their case -> refuse a
            financial question) proving context carry-forward AND the refusal.

Works:    `python -m app.api.run_eval` -> PASS RATE 28/28 = 100% offline, then prints the
          multi-turn transcript with the provenance crime_nos per turn. `pytest` -> 109
          passed (14 new in tests/api: loop mechanics, tool_result plumbing/ids, parallel
          tool calls, RBAC-denial-not-leaked, empty-provenance refusal, multi-turn, the
          max-rounds valve, and /chat + /chat/stream via TestClient). ruff clean. FastAPI
          boots; openapi shows /chat + /chat/stream.

Broken:   Nothing. Notes for whoever runs this / builds P19:
          - The offline eval proves the LOOP (plumbing, provenance, RBAC, refusal). It does
            NOT prove the model PICKS the right tool — that needs `run_eval --live` with a
            real key (ANTHROPIC_API_KEY unset here; AnthropicClient also accepts an ambient
            credential). Same 28 cases, same grader, so it's ready the moment a key exists.
          - ENV GOTCHA (cost me time): tests/eval need POSTGRES_HOST=localhost — config
            defaults host to `db` (the docker-compose service name), which doesn't resolve
            outside compose. Also the project venv is backend/.venv and it did NOT have the
            anthropic SDK or pip; I ran `.venv/bin/python -m ensurepip` then installed
            anthropic>=0.40 (added to pyproject deps). System python != the venv.
          - Added ruff flake8-bugbear extend-immutable-calls for fastapi.Depends/Query/
            Path/Body so the standard FastAPI default-arg idiom stops tripping B008.
          - The principal comes from the request body for now. RBAC is at the tool boundary
            regardless, so a forged principal can only NARROW what's visible. Real auth/SSO
            wiring is a later concern; documented in routes.py.

Next:     The chat spine is demoable end-to-end. Highest-leverage next:
          - P12 (network tools) / P13 (trend + hotspot tools) widen the catalogue the loop
            can already call — every new Tool auto-registers into /chat and needs one line
            in build_registry + one eval question (test_every_tool_has_a_question enforces
            this, so an unquestioned tool fails the suite).
          - P19 (frontend shell) can consume /chat + /chat/stream now.
          Recommend P13 next (trends close PS1 §3, currently 🔴) then P19 for a visible demo.
```

### 2026-07-19 · Claude (Thiru) · Catalyst pivot (hosting + LLM provider)
```
Did:      Repointed hosting + LLM requirements at Zoho Catalyst (hackathon platform
          partner; user wants Catalyst maximized and a Catalyst-console key to power
          the demo instead of an Anthropic key).
          - app/api/llm.py: OpenAICompatClient — speaks OpenAI chat-completions wire
            format (incl. tool calling) over httpx against Catalyst UniAI or any
            compatible gateway. Translates our internal Anthropic-block message list
            to the OpenAI shape per request and maps responses back, so the
            orchestrator/tools/eval are provider-agnostic and UNTOUCHED.
            client_from_settings() dispatches on LLM_PROVIDER (uniai default |
            anthropic); routes.get_llm_client and run_eval --live both use it.
          - config.py: LLM_PROVIDER + UNIAI_BASE_URL/API_KEY/MODEL/CHAT_PATH/
            AUTH_SCHEME (bearer | zoho-oauthtoken) + CORS_ORIGINS (for the Slate
            frontend origin). compose passes them all through.
          - serve.py + app-config.json + Dockerfile CMD: AppSail-ready. serve.py binds
            X_ZOHO_CATALYST_LISTEN_PORT (AppSail kills instances not bound in 10s),
            falls back to 8000 so compose/dev is unchanged (compose adds --reload).
            app-config.json = python_3_12, 1024MB, no env_variables (deliberate — the
            linked-app redeploy would DELETE console-set secrets not listed there).
          - DEPLOYMENT-CATALYST.md: full service mapping (AppSail/Slate/Job
            Scheduling/SmartBrowz/Stratus/Cache/Auth), 3 deploy flows, env var table.
          - CLAUDE.md stack section updated to match.

Works:    pytest -> 119 passed (10 new in tests/api/test_uniai_client.py, all offline
          via httpx.MockTransport: auth schemes, message/tool translation both
          directions, finish_reason=tool_calls -> stop_reason=tool_use, error paths,
          and a full orchestrator round-trip over a fake gateway hitting the real
          registry/RBAC/provenance). ruff clean. App boots, provider default = uniai.

Broken:   Nothing in code, but ONE UNVERIFIED ASSUMPTION, flagged in the decision
          table: UniAI's wire format. Zoho docs 403 to fetchers and Catalyst's own
          agent-skills repo (checked 2026-07-19) documents no LLM gateway API, so the
          client targets the de-facto OpenAI-compatible gateway shape with CHAT_PATH/
          AUTH_SCHEME as escape hatches. THE MOMENT a real UniAI key exists, run:
            UNIAI_BASE_URL=... UNIAI_API_KEY=... UNIAI_MODEL=... \
              python -m app.api.run_eval --live
          28-case eval + multi-turn transcript against the live gateway. If the shape
          differs, fix ONLY OpenAICompatClient. Also: the chosen UniAI model MUST
          support function calling or the whole tool loop is dead — check first.

Next:     Unchanged from P14: P12/P13 to widen the tool catalogue, or P19 (frontend,
          now with a Slate deployment target). Whoever does P24 (PDF): SmartBrowz
          first, WeasyPrint fallback. P17a: use Catalyst Job Scheduling, not cron.
```

### 2026-07-19 · Claude (Thiru) · Catalyst LLM = QuickML serving + prompted tool mode
```
Did:      Follow-up to the Catalyst pivot after the constraint got sharper: Catalyst is
          the ONLY cloud, so the LLM must be Catalyst-native. Researched Catalyst's AI
          surface — the concrete hosted-LLM offering is QuickML LLM Serving (Qwen 2.5,
          POST endpoint + Zoho OAuth). No component literally named "UniAI" is findable
          in Catalyst docs / agent-skills; kept UNIAI_* env names as generic config.
          - Reoriented OpenAICompatClient to target QuickML serving; added a two-mode
            tool-calling design because QuickML tool-calling support is undocumented:
              * prompted (NEW DEFAULT): tool catalogue + strict JSON protocol injected
                into the system prompt, reply parsed into a tool call or final answer.
                Tool results are fed back as "TOOL RESULT: <json>" user text (no
                role:"tool"). Works with ANY chat model — the loop runs on a plain Qwen
                with zero native tool API. Tolerant parser (strips ``` fences, extracts
                the {...}, degrades to a plain answer if non-JSON).
              * native: OpenAI tools/tool_calls, for endpoints that support it.
          - config: UNIAI_TOOL_MODE (default prompted); compose passes it through.
          - Docs: DEPLOYMENT-CATALYST.md LLM section rewritten (QuickML endpoint, Zoho
            OAuth, prompted-vs-native, day-one run_eval --live); CLAUDE.md stack line.

Works:    pytest -> 126 passed (7 new: prompted-mode catalogue injection, JSON tool-call
          parse, final-answer + code-fence tolerance, non-JSON degrade, tool_result-as-
          text rendering, bad-mode rejection, AND a full orchestrator round-trip in
          prompted mode over a fake Qwen — no native tools, real registry/RBAC/
          provenance). Existing native-path tests pinned to tool_mode="native". ruff
          clean. Default provider=uniai, default tool_mode=prompted.

Broken:   Nothing. Same standing caveat: QuickML serving's exact request/response body is
          unverified (assumed OpenAI-shaped). Day the model+key exist, run
          `python -m app.api.run_eval --live` with UNIAI_AUTH_SCHEME=zoho-oauthtoken.
          If native tool calling works there, set UNIAI_TOOL_MODE=native for quality.
          Note QuickML/AutoML is region-limited (not in EU/AU/IN/JP/SA/CA per Catalyst
          docs) — confirm the hackathon DC has it, else the fallback is another Catalyst
          OpenAI-compatible endpoint with the same client.

Next:     Unchanged: P12/P13 tools or P19 UI (Slate). No LLM work remains until a real
          Catalyst model endpoint is available to run the live eval against.
```

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

### 2026-07-18 · Claude (Thiru) · P11
```
Did:      Built app/tools/compliance.py on the P9 framework. chargesheet_deadline_watch
          (default-bail board: arrest + no chargesheet, 90/60-day windows, bucketed by
          urgency, max_overdue_days bound so stale cases don't drown the signal) and
          registration_delay_report (per-unit info->registered lag, outlier flagging via
          mean+z*std, k-anon, integrity caveat). Added app/tools/catalog.py (build_registry
          — the canonical registry P14 uses); `python -m app.tools` prints its schemas.

Works:    pytest tests/tools/ -> 19 passed (9 new). Live: state-wide board flags 1,720
          actionable cases (250 critical, 126 warning, 1,344 recently breached); the demo
          beat "148 heinous cases at day 75+" surfaces. reg-delay flags 9 outlier stations.
          Full suite 92, ruff clean. RBAC/provenance/audit all inherited & working.

Broken:   Nothing. Notes:
          - DATA REALISM: P2 leaves ~old open+arrested cases (2022 arrests, no chargesheet)
            that are 1,600+ days "overdue". Those aren't real default-bail risks (accused
            released long ago). The board's max_overdue_days (default 45) filters them out;
            raise it to audit history. If P2 is regenerated, consider closing more old cases.
          - catalog.build_registry() currently includes the P9 demo get_case. P10 should
            REPLACE it with a person_cluster-backed get_case/get_person (resolved profile
            across FIRs), not the accused_master_id demo version.

Next:     P10 (retrieval tools: get_case, search_cases, get_person via person_cluster,
          get_case_timeline, get_chargesheet_status) is the backbone the chat needs, and
          person_cluster is now populated + measured so get_person can return the resolved
          cross-FIR profile. P12 (network tools) also unblocked. P14 (orchestration) is the
          merge point once a few retrieval tools exist. Recommend P10 next.
```

### 2026-07-18 · Claude (Thiru) · P10
```
Did:      Built app/tools/retrieval.py — the 6 retrieval tools (get_case, search_cases,
          get_person, search_persons, get_case_timeline, get_chargesheet_status) on the
          P9 framework. get_person is the important one: resolved profile across ALL
          linked FIRs via person_cluster/person_cluster_member (NEVER accused_master_id
          as identity), with per-link confidence. catalog.build_registry() now has 9
          real tools; retired the demo get_case.

Works:    pytest tests/tools/ -> 31 passed (12 new). Live: get_person on a 34-FIR
          offender ("Raju S/o Venkatappa", written Venkatanna/Venkatappa/Wenkatappa)
          returns the cross-FIR profile; an SP of one district sees 4 in-scope FIRs,
          30 hidden out-of-scope. get_case links accused -> person_cluster_id. Timeline
          shows incident->info->registered->arrest(51d)->chargesheet(89d). Full suite 95,
          ruff clean.

Broken:   Nothing. One GOVERNANCE tension to flag for P14/demo (not a bug):
          get_person/search_persons are person_level, so analyst/policymaker (state,
          aggregate-only) are DENIED, and SP/DySP/SHO are scope-limited to their units.
          Net effect: NO role can see a repeat offender's FULL cross-district profile
          with person-level detail. That's correct per PLAN §6, but the flagship demo
          beat ("same person across a dozen stations") needs a principal whose scope
          actually spans those stations. For the demo, use an SP/DySP whose district/
          subtree contains the seeded offender's FIRs, OR consider (P25) seeding the
          demo repeat-offender within ONE district's stations. If a "state investigator"
          role that sees person-level state-wide is wanted, add it to base.Role +
          the scope/PERSON_TOOL_DISABLED sets — but that's a policy decision, don't do
          it silently.

Next:     P14 (orchestration ★) is now the high-leverage merge point: 9 tools exist
          (retrieval + compliance), person_cluster is populated. P14 = FastAPI /chat +
          the Claude tool-calling loop over catalog.build_registry(), system prompt
          enforcing "never author a fact", streaming, provenance chain, eval set incl.
          unanswerable questions. That makes the whole thing demoable end-to-end.
          Alternatively P12 (network tools) or P13 (trends) to widen the catalogue first.
          Recommend P14.
```

### 2026-07-19 · Claude (Opus) · UI/UX redesign (frontend only)
```
Did:      Complete presentation-layer redesign of frontend/ to a premium, culturally-rooted
          GovTech aesthetic (Karnataka heritage palette, sarvam.ai-style clean typography).
          ZERO backend/API/prop/data-contract change — same tools render, same interactions.
          DESIGN SYSTEM (frontend/src/index.css, full rewrite):
          - Tokens as CSS custom properties; dark (default) + light via [data-theme] on <html>.
            Toggle in top bar, persisted to localStorage("ksp-theme"), no-flash init script in
            index.html. Warm-tinted dark neutrals (bg #0E1015 → border-strong #3A4350);
            sandalwood/ivory light surfaces.
          - Palette: Mysore GOLD (#E0A21A, hover #C98A00, soft #F2C94C) = brand/primary/active;
            Hampi TERRACOTTA (#C2643D/#B5533C) = hotspots/heat/danger; Kaveri TEAL
            (#0F5E70/#12657F/#2E96AE) = info/links/co-offender nodes. Semantic success/warn.
          - Typography via @fontsource (offline, bundled — NOT a CDN): Outfit (display/headings),
            Inter (body/UI), JetBrains Mono (IDs/CrimeNos/numbers only — moved OFF all-mono),
            Noto Sans Kannada (in body stack so Kannada voice/text output renders). Type scale
            11–40, spacing 4px scale (--space-1..10), radii + subtle elevation tokens.
          - Motifs: two inline-SVG data-URI patterns (Kasuti/Hoysala stepped-star lattice +
            diagonal weave) used at ~0.05 opacity on the top bar, empty states, and card
            headers via a .motif helper + ::before layers; a gold→terracotta→teal accent strip
            under the top bar and case-drawer header. Tasteful, never over the data.
          - Micro-interactions: message ease-in, tool-chip slide-in, tab underline crossfade,
            button press states, focus-visible gold rings, hover transitions; all wrapped in a
            prefers-reduced-motion guard. Custom scrollbars.
          LAYOUT (App.tsx): refined top bar (gold emblem plate w/ stepped-star, brand, scope
            PILL, premium role switcher w/ custom caret, dark/light toggle) + slim footer status
            strip. Two-pane workspace unchanged in behaviour; tabs got icons + pulse badges +
            crossfaded pane content + beautiful empty states (motif + glyph). Responsive stack
            under 860px. Kept the role→remount-chat linkage and answer→repaint-panes logic.
          COMPONENTS (restyled, props/behaviour preserved): ChatPane (bubbles, streaming cursor,
            tool chips, icon send w/ spinner, banner w/ alert icon, suggestion pills),
            EvidencePane (provenance cards, mono CrimeNo chips → CaseDrawer), NetworkGraph (SVG
            gold seed w/ glow gradient + teal co-offenders, weight-scaled edges), HotspotMap (SVG
            graticule frame + terracotta heat, coverage-honesty note kept verbatim), CaseDrawer
            (sticky gradient header, tag rows, Esc-to-close, kv grid). Added src/icons.tsx
            (lightweight inline SVG set — no icon dependency).
          NEW DEPS: @fontsource/{outfit,inter,jetbrains-mono,noto-sans-kannada} only. No
            MapLibre/Cytoscape/torch — SVG panes stayed SVG as required.

Works:    `npx tsc --noEmit` clean. `npm run build` (tsc -b && vite build) clean — built in
          ~0.7s, index.js 162.67 kB (gzip 52.77) + index.css 73.01 kB (gzip 27.58), fonts
          bundled as woff/woff2 assets (offline). `docker compose build frontend` from repo
          root — RAN and SUCCEEDED (image ksp-crime-intelligence-frontend:latest built; needed
          elevated/network perms — the sandboxed `docker info` reports the daemon down, but the
          daemon is reachable when run unsandboxed). Files changed: index.css, main.tsx (font
          imports), index.html (theme init + meta), App.tsx, icons.tsx (new), and all five
          components under src/components/. package.json (+4 @fontsource deps). Code NOT
          committed (only this log + the earlier claim commit, per the task).

Broken:   Nothing. Notes:
          - Behaviour/data contracts untouched: api.ts, /api/* paths, SSE parsing,
            extractGraph/extractGeo, component props all identical. Streaming chat, tool chips,
            role switch, evidence CrimeNo→CaseDrawer, network/map tabs, 503 LLM banner, and
            403 out-of-jurisdiction all still work as before.
          - Two deviations from PLAN's "dark/dense/operational" (light mode + off all-mono) are
            logged in "Decisions that deviate from PLAN.md". Dark stays the default and it's
            still dense.
          - The chat itself still needs the LLM configured (UNIAI_* or LLM_PROVIDER=anthropic);
            unchanged — panes/evidence/role-switch/case-drawer work regardless.

Next:     P20 upgrades the SVG panes to MapLibre/Cytoscape — the new palette tokens
          (--gold/--kaveri/--heat, node/edge classes) are the intended colours to carry over.
          A native-speaker pass on Kannada templates (P22) can now rely on the Noto Sans
          Kannada pairing already wired into the body font stack.
```

### 2026-07-19 · Claude (Opus) · UI/UX revision + FE refactor
```
Did:      Second design pass — the first redesign was verdict'd "still looks AI-generated /
          vibe-coded". Rebuilt the presentation into a bespoke operational console AND
          refactored frontend/src for real engineering hygiene. ZERO backend/contract change:
          /api/* paths, request/response JSON, SSE parsing, and all wire types are byte-for-
          byte identical (api.ts was only reorganised into modules, not altered on the wire).

          STACK CORRECTION (was a live confusion): the frontend is **React 18 + Vite + TS**,
          NOT Next.js. No framework migration; none needed or wanted.

          DE-AI DESIGN (what removed the "AI smell", index.css full rewrite):
          - Killed the tells: the gold→terracotta→teal rainbow accent strips (top bar +
            drawer), the Kasuti motif stamped onto the top bar / every card / every empty
            state, the gradient emblem plate, the radial-gradient "glows" behind the SVG
            panes and viz backgrounds, drop-shadows on cards/bubbles, the infinite pulse
            badges, and the everything-is-a-pill radii. These are the generic templated
            choices that read as vibe-coded.
          - Replaced with an opinionated system: one dominant calm surface (cool graphite
            near-black canvas, NOT the previous warm "sandalwood" tint), structure carried by
            crisp 1px hairlines instead of shadows/gradients, and gold used SPARINGLY as a
            signal only (active tab underline, focus ring, primary send button, tab data-dot,
            seed graph node, the FIR number in the drawer). Terracotta strictly = heat/danger;
            teal = links/interactive. Deliberate small radii (4/6/9px), a real 4px spacing
            grid, a tightened type scale (11–24, dropped the 40px display), tabular mono for
            all IDs/counts/metrics.
          - Chat is now an analyst transcript, not a symmetric two-bubble messenger: user
            queries are compact right-aligned blocks, assistant answers are full-width prose
            with a quiet label + an inline "Traced" tool-chip row. This asymmetry is the
            single biggest "not-a-chatbot-template" move.
          - Heritage kept as exactly ONE restrained detail x2: the line-only Kasuti stepped-
            diamond brand glyph, and a single thin engraved rule (one diamond) as the empty-
            state divider. Nothing else is themed.
          - Real states throughout: hover/active/focus-visible (gold rings), streaming cursor,
            busy spinner in the send button, teaching empty states, error banner (role=alert),
            disabled states; motion is subtle and under a prefers-reduced-motion guard.
            A11y: semantic landmarks (header/main/aside/section/footer), aria-labels on all
            icon-only buttons, Enter-to-send, Esc-closes-drawer, AA-minded contrast.

          MODULAR REFACTOR (Part B — was one flat components/ dir + a monolithic api.ts):
          New src/ tree:
            api/         client.ts (fetch/SSE), types.ts (all wire types), extract.ts
                         (tool→pane narrowing, the only place that knows tool payload shapes),
                         index.ts barrel
            hooks/       useTheme, useDemoRoles, useChatStream (owns streaming/history/patch
                         logic that used to live inside ChatPane), usePaneData (the App memo)
            components/  presentational primitives: icons, IconButton, Chip, Pill, Tabs,
                         EmptyState, KeyValue, Drawer, ThemeToggle
            features/    chat/ (ChatPane, ChatMessage, ChatComposer, ToolTrace, suggestions),
                         evidence/ (EvidencePane, ProvenanceCard), network/ (NetworkGraph),
                         map/ (HotspotMap), roles/ (RoleSwitcher), case/ (CaseDrawer),
                         layout/ (TopBar, StatusBar, Workspace)
            lib/         constants.ts (magic numbers lifted: theme key, history limit, graph/
                         map dims + bbox, chip caps), format.ts (count/humanize/errorMessage)
          App.tsx is now a thin composition (~50 lines) of hooks + feature components. Views
          are declarative; side-effect/stateful logic lives in hooks. Types tightened: the old
          `data?: any` / `e: any` are gone — ToolData = Record<string,unknown> narrowed via
          guards in extract.ts, CaseRecord/AccusedRef typed for the drawer, errors handled as
          unknown. No implicit any. Removed the unused `@/*` tsconfig path alias (dead config).

          TOOLING ADDED (was: "lint" = just tsc): ESLint 9 flat config (@eslint/js +
          typescript-eslint + react-hooks + react-refresh + eslint-config-prettier) and
          Prettier, both standard/minimal. Scripts: typecheck (tsc), lint (tsc && eslint .),
          format / format:check. Added frontend/.dockerignore (node_modules/dist/.git) — the
          Dockerfile's `COPY . .` runs AFTER `npm install`, so without it a host node_modules
          (now present because we install locally) would clobber the image's Linux modules.

          FONTS unchanged set but trimmed to used weights only (Outfit 600 wordmark; Inter
          400/500/600; JetBrains Mono 400/500/600; Noto Sans Kannada 400/500) — still bundled
          via @fontsource, no CDN. No new runtime deps; SVG panes stayed SVG.

Works:    All run this pass, all green:
          - `npx tsc --noEmit` → clean.
          - `npm run lint` (tsc --noEmit && eslint .) → clean, 0 errors/0 warnings.
          - `npm run format:check` → all files match Prettier.
          - `npm run build` (tsc -b && vite build) → clean; index.js 165.13 kB (gzip 53.68) +
            index.css 59.87 kB (gzip 25.89), fonts bundled as woff/woff2. Built in ~0.4s.
          - `docker compose build frontend` (repo root) → RAN and SUCCEEDED (needed elevated
            perms; the sandboxed `docker info` reports the daemon down but it's reachable
            unsandboxed, same as last pass). `npm install` in-image added 181 pkgs, 0 vulns,
            image ksp-crime-intelligence-frontend:latest built.

Broken:   Nothing. Notes:
          - Behaviour/contracts untouched: streaming chat + inline tool chips, role switch
            remounts chat with a new principal (RBAC demo), evidence CrimeNo chips → CaseDrawer
            via POST /api/case incl. honest 403, network/map SVG panes from extractGraph/
            extractGeo, ask→panes-repaint linkage, 503 LLM banner. Dark default + light toggle
            + localStorage persistence (ksp-theme) all preserved.
          - `make lint` runs `npm run lint`, which is now tsc + eslint (was tsc only) — a
            strict improvement, still passes. Chat still needs the LLM configured (UNIAI_* or
            LLM_PROVIDER=anthropic); panes/evidence/role-switch/case-drawer work regardless.
          - Code left UNCOMMITTED per the task; only this log + the earlier claim commit went in.

Next:     Unchanged: P20 upgrades the SVG panes to Cytoscape/MapLibre — the new token names
          (--accent/--link/--heat, .graph-node/.graph-edge/.map-hotspot classes) are the
          colours to carry over. P16→P17→P17a→P20→P25 remains the demo path.
```

### 2026-07-19 · Claude (Opus) · UI upgrade (bento grid)
```
Did:      Reorganised the frontend layout around a BENTO GRID and added tile primitives.
          ZERO backend/contract change: /api/* paths, request/response JSON, SSE parsing,
          and every wire type in src/api/ are byte-for-byte identical — presentation only.

          WHY BENTO (over the two other options offered):
          - For a data-dense operational/analytics console judged by government stakeholders,
            a bento grid gives modern structure, clear information hierarchy, and a premium
            dashboard feel without hurting legibility.
          - Neumorphism was rejected: low-contrast extruded surfaces fail AA and read dated.
          - Heavy glassmorphism/liquid-glass was rejected across data surfaces: translucency
            over maps/graphs/evidence muddies text. Kept as ONE restrained accent only —
            a subtle backdrop blur on the drawer scrim (with the solid --overlay-scrim as the
            fallback), never on a data pane.

          LAYOUT: the old two-column workspace (chat | tabbed panes) is now a 3-tile bento of
          intentional, varied sizes on a recessed --canvas:
            - tile-chat     : tall PRIMARY tile spanning both rows (left) — the conversation.
            - tile-session  : compact context tile (top-right) — NEW. Shows the active RBAC
                              principal + scope (moved out of the top bar to avoid duplicating
                              the role switcher) plus live signals from the last answer:
                              Tools run / FIRs cited / Rows examined (or a red Denied count
                              when a tool was refused). Tabular mono numerals.
            - tile-analysis : large tile (bottom-right) — the existing Evidence/Network/Map
                              tabbed pane, with the tab strip now serving as the tile header.
          Responsive: 2-col reflows to a slightly tighter split ≤1080px, then collapses to a
          single scrolling column ≤900px (chat 62vh, analysis 72vh) — reflows, doesn't break.

          NEW PRIMITIVES / COMPONENTS:
            - components/Tile.tsx      — the reusable bento tile (header slot: `title`+`actions`
                                         OR a custom `head` node like the tab strip; body slot
                                         with `tile-flow`/`tile-pad` variants). Everything is
                                         composed from this, so radii/hairlines/elevation stay
                                         consistent.
            - features/layout/SessionPanel.tsx — the context tile (memoised signal summary over
                                         toolCalls; reuses the Pill primitive for the role badge).
          WIRED: ChatPane and Workspace now render inside <Tile>; App composes the three tiles
          under <main className="bento">; TopBar dropped its scope Pill (now in the Session tile).

          TOKENS ADDED (index.css): --r-tile (10px), --bento-gap (12px), --tile-head-h (44px),
          and per-theme --tile-shadow (restrained: a hairline does the real work, the shadow
          only lifts the tile off the canvas) + --canvas (recessed bento background, one step
          below --bg in both themes). Tiles are --surface on the --canvas so hairline + subtle
          elevation read as separate designed surfaces. No rainbow strips, no glows, no
          everything-rounded — the de-AI'd register from the last pass is preserved.

          A11y: tiles are <section aria-label>; icon buttons keep aria-labels; focus-visible
          gold rings unchanged; the glass note has a solid fallback and text never sits on blur;
          motion additions are none beyond existing (all still under prefers-reduced-motion).

Works:    All run this pass, all green:
          - `npx tsc --noEmit` → clean.
          - `npm run lint` (tsc --noEmit && eslint .) → clean, 0 errors / 0 warnings.
          - `npm run format` then `npm run format:check` → all files match Prettier.
          - `npm run build` (tsc -b && vite build) → clean; 71 modules, index.js 166.94 kB
            (gzip 54.17) + index.css 62.32 kB (gzip 26.43), fonts bundled offline. ~0.4s.
          - `docker compose build frontend` (repo root) → RAN and SUCCEEDED (elevated perms;
            image ksp-crime-intelligence-frontend:latest built/unpacked). Repo root clean —
            no stray root-level package-lock.json.

Broken:   Nothing. Notes:
          - Behaviour/contracts untouched: streaming chat + inline tool chips, role switch
            remounts chat with a new principal (RBAC demo), evidence CrimeNo chips → CaseDrawer
            via POST /api/case incl. honest 403, network/map SVG panes from extractGraph/
            extractGeo, ask→panes-repaint linkage, 503 LLM banner. Dark default + light toggle
            + localStorage persistence (ksp-theme) all preserved. Chat still needs the LLM
            configured (UNIAI_* or LLM_PROVIDER=anthropic); the tiles/evidence/role-switch/
            case-drawer work regardless.
          - Scope readout moved from the top bar into the Session tile (control vs. status
            split) — a deliberate de-duplication, not a lost feature.
          - Code left UNCOMMITTED per the task; only this log + the earlier claim commit went in.

Next:     Unchanged: P20 upgrades the SVG panes to Cytoscape/MapLibre inside the existing
          tile-analysis tile (drop-in — the tile header/body slots stay). P16→P17→P17a→P20→P25
          remains the demo path.
```
