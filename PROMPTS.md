# Claude Code Prompt Sequence

**33 prompts in execution order.** Work top to bottom. Copy-paste each into Claude Code.

Prompt IDs are stable identifiers, not positions — the `a`-suffixed ones were added after
auditing against PS1 and are now slotted where they actually belong. IDs match the status table
in `CONSISTENCY.md`, so don't renumber them.

### How to use this

- **Read `CONSISTENCY.md` and claim the prompt before you start.** Two people building the same
  thing is the expensive failure on this project.
- **One prompt = one testable deliverable.** Verify each against its acceptance criteria before
  moving on. Don't build phase 3 on a phase 1 that doesn't run.
- Commit after every prompt that passes. When one goes badly, `git reset --hard` beats
  negotiating your way out of a tangled tree.
- For the ★ prompts, start in **plan mode** (`shift+tab` twice) — these are the ones where a
  wrong architectural choice costs a day.
- `/clear` between phases. The files on disk are the state, not the conversation.
- Report symptoms, not fixes. "The phonetic matcher collapses Ramesh and Ramya" gets a better
  outcome than prescribing a threshold change.

### At a glance

| Phase | Prompts | Gate |
|---|---|---|
| 0 · Foundation | P1 → P2 → P3 → P4 → P4a | Database loaded, synthetic data with ground truth |
| 1 · Entity resolution | P5 → P6 → P7 → P7a → P8 | **`person_cluster` exists with a measured F1** |
| 2 · Tools & chat | P9 → P9a → P10 → P10a → P11 → P12 → P13 → P13a → P14 | Demoable end to end |
| 3 · Intelligence | P15 → P16 → P17 → P17a → P18 | The analytical layer |
| 4 · Interface | P19 → P20 → P19b → P19a → P21 | Looks like a product |
| 5 · Language & export | P22 → P23 → P24 | Judge-facing polish |
| 6 · Demo | P25 | |

---
---

# Phase 0 — Foundation

## P1 — Repo scaffold and database
> Blocks everything.

```
Read PLAN.md and CLAUDE.md.

Set up the project foundation:
- docker-compose with Postgres 16 + PostGIS + pgvector, and a Makefile with
  `make up`, `make down`, `make psql`, `make reset`
- Python project with uv, FastAPI, SQLAlchemy, Pydantic v2, pytest
- The full DDL for the KSP schema in db/schema.sql, translated from the ER diagram in
  PLAN.md. Resolve the documented type mismatches (standardize on VARCHAR for ActCode
  and SectionCode), add the missing primary key on Section, and model the two undefined
  tables (Inv_OccuranceTime, inv_arrestsurrenderaccused) with a comment marking each
  inferred column as an assumption.
- A separate db/derived.sql for our own tables — start with just person_cluster and
  person_cluster_member. Keep our derived layer strictly separate from the KSP schema.

Acceptance: `make up && make reset` gives me a running database with every table created
and no errors. Show me the table list when done.
```

## P2 ★ — Synthetic data generator
> Needs P1. **Do not treat this as throwaway scaffolding** — the hidden ground truth is the
> only way to measure entity resolution, and that measurement is your headline number.

```
Build ingest/synth/ — a synthetic KSP FIR generator. This unblocks all development before
the real dataset arrives, and it is the only way to measure entity resolution accuracy.

Requirements:
- Generate realistic Karnataka data: real district and taluk names, plausible police station
  names, lat/long inside actual district boundaries, Kannada-origin person names.
- Well-formed CrimeNo values matching the documented format, including a realistic share of
  Zero FIRs (category 8) and UDRs (category 3).
- Realistic date chains: incident → info received → registered → arrest → chargesheet, with
  plausible and occasionally pathological delays.
- cstype outcomes distributed realistically across A/B/C.
- BriefFacts narratives: templated by crime type, mixed English / Kannada / transliterated
  Kannada, with recognisable modus operandi patterns embedded so MO clustering has real
  signal to find.

Critically — the part that matters most:
- Maintain a hidden ground-truth person registry. A single synthetic person recurs across
  multiple FIRs with DELIBERATELY CORRUPTED name variants: spelling drift (Ramesh /
  Ramesha / Rameshu), transliteration variants, "@" aliases, patronymic sometimes present
  and sometimes absent, age drifting ±2 years from true.
- Write the ground truth to a separate file that the ER pipeline must never read.
- Include repeat offenders and co-offending groups so network analysis has something real
  to detect.
- Include people who appear as a victim in one FIR and an accused in another — we need this
  for the victim-offender overlap analysis later.

Make the volume configurable. Acceptance: `python -m ingest.synth --cases 50000` loads the
database, and the ground-truth file lets me compute how many distinct real people exist.
```

## P3 — Ingest and CrimeNo parsing
> Needs P1.

```
Build ingest/loader.py:
- Load from CSV/Excel into the KSP schema, tolerant of missing columns and dirty values
- A CrimeNo parser that decomposes into category/district/station/year/serial, and validates
  the parsed parts against the FK columns — report mismatches rather than silently accepting
- A data quality report: null rates per column, FK violations, date ordering violations
  (e.g. registered before incident), lat/long null rate and out-of-Karnataka outliers

Acceptance: run it against the synthetic data and print the quality report. I want to see the
lat/long null rate specifically.
```

## P4 — Translation layer
> Needs P3. Everything downstream reads `BriefFacts_en`, so this gates Phase 3.

```
Build ingest/translate.py:
- Detect the language of each BriefFacts row (Kannada script / Roman / code-mixed)
- Populate a BriefFacts_en column via claude-sonnet-5, batched and concurrent, with caching
  so re-runs are cheap and resumable after a crash
- Never modify the original BriefFacts

Acceptance: processes 50k rows without blowing up on rate limits, and re-running skips
already-translated rows.
```

## P4a — External socio-economic data
> Independent of P2/P3 — **good candidate to run in parallel** while the other person does ER.
> Closes PS1 §4, which is otherwise unbuildable: urbanization, migration, economic stress and
> education do not exist anywhere in the KSP schema.

```
Build ingest/socioeconomic.py — district-level indicators for Karnataka, joined to crime data.

Sources (public, district-level, keep every one cited in a manifest):
- Census 2011: population, density, urban/rural split, literacy rate, SC/ST proportion,
  worker participation, migration where available
- Any newer district-level indicators you can find for economic stress proxies
  (unemployment, per-capita income, NITI Aayog district indicators)

Requirements:
- A district_indicators table keyed to the KSP DistrictID, with a mapping table because the
  names will not match cleanly (Bangalore/Bengaluru, district splits since 2011). Hand-verify
  the mapping and log anything ambiguous.
- Crime RATES per 100k, not raw counts — this is the whole point. Raw counts just rediscover
  which districts have the most people.
- A tool: socioeconomic_correlation(crime_head, indicator) returning correlation with
  confidence intervals and the underlying scatter data for plotting.

Every output must carry the caveat that these are ecological correlations at district level
and do not support individual-level inference. Put that in the tool's returned metadata, not
just a comment — it should reach the user.
```

---
---

# Phase 1 — Entity resolution

> **This is the project.** `AccusedMasterID` is a per-FIR row ID, not a person. Sections 2, 5,
> and half of 6 and 8 of the problem statement are uncomputable until `person_cluster` exists.
> Do not rush past this phase.

## P5 ★ — Name parsing and normalization
> Needs P2. This module's quality sets the ceiling for the entire project.

```
Build er/names.py. Read the entity resolution section of PLAN.md first.

Indian FIR name fields carry structure inside free text. Parse AccusedName / VictimName /
ComplainantName into components:
- given name
- alias (the "@" convention: "Ramesh @ Rami")
- patronymic and its relation type (S/o, D/o, W/o, C/o)
- honorifics to strip

Then normalize:
- Kannada → Roman transliteration (use indic-transliteration or AI4Bharat IndicXlit)
- Handle Kannada terminal-vowel variation: Ramesh/Ramesha/Rameshu, -appa/-anna/-amma suffixes
- Produce a phonetic key: Double Metaphone over the transliteration PLUS a Dravidian rule set
  (collapse aspirates, th↔t, dh↔d, sh↔s, v↔w, retroflex↔dental). Plain Soundex is tuned for
  English surnames and will fail on these names.

Write thorough unit tests with real Kannada name variants. I would rather this be slow and
correct than fast and approximate.

Acceptance: tests pass, and `Ramesh @ Rami S/o Krishnappa` parses into all four components.
```

## P6 — Blocking and pairwise scoring
> Needs P5.

```
Build er/blocking.py and er/scoring.py.

Blocking (never compare all pairs): candidate blocks on phonetic key of first token, on
district, and on shared arrest event via inv_arrestsurrenderaccused.

Pairwise scorer producing a 0–1 probability from:
- Jaro-Winkler on the normalized name (high weight)
- Patronymic match when both present (very high)
- Alias overlap (very high)
- Age consistency: estimate birth year from AgeYear + CrimeRegisteredDate, require within ±2y
- Gender: a hard gate, not a weight
- Geography: same station / district / adjacent district (medium)

Make the weights configurable in one place so I can tune them. Log the per-signal contribution
for every pair so I can debug why two records did or didn't match.

Acceptance: scoring 50k records completes in under two minutes, and I can dump the top 50
scored pairs with their signal breakdown.
```

## P7 ★ — Collective resolution
> Needs P6. **The novel technical contribution.** Identity and network solved jointly.

```
Build er/resolve.py — the novel part. Read PLAN.md §2 stage 5 carefully.

Identity and network get solved jointly, each improving the other:
1. Build the co-offending graph from inv_arrestsurrenderaccused (networkx)
2. Run initial pairwise scoring
3. Propagate: if two candidate records share an already-resolved co-offender, boost their
   score. Two "Ramesh" records arrested alongside the same resolved "Suresh" are far more
   likely to be the same Ramesh.
4. Re-resolve with boosted scores. Iterate 2–3 rounds or until stable.

Then cluster:
- ≥0.85 auto-merge
- 0.60–0.85 → review_queue table, NEVER auto-merged
- Persist person_cluster_id, confidence, and the merge evidence (which signals fired, which
  records, which co-offenders) for every link

Acceptance: person_cluster is populated, and for any cluster I can ask "why are these the
same person" and get the evidence back.
```

## P7a — Victim-offender overlap
> Extends P7. Closes PS1 §2's "links between accused, **victims**, locations…"

```
Verify and extend the entity resolution pipeline to resolve victims and complainants into the
SAME person_cluster namespace as the accused, not a separate one.

This unlocks the victim-offender overlap: the same individual appearing as a victim in one FIR
and an accused in another. It's one of the most robust findings in criminology and it is
completely invisible in the raw schema.

Add a tool: victim_offender_overlap(district?, crime_head?) returning people who appear in both
roles, with their case history in each.

Handle the obvious risk: this is sensitive. Restrict the tool to investigator and supervisor
roles, and never surface victim identities to analyst or policymaker roles.
```

## P8 — ER evaluation harness
> Needs P7 + P2's ground truth. **Produces your headline number.**

```
Build er/evaluate.py. Load the synthetic ground truth and score the pipeline:
- Pairwise precision / recall / F1
- Cluster-level metrics too
- A breakdown of what we get wrong: which corruption types (spelling drift, alias, missing
  patronymic, age drift) cause the most misses
- Measure the lift from collective resolution: run with propagation off, then on, and report
  the delta

Acceptance: one command prints the full report. The collective-resolution delta is the number
that goes on the slide, so make it prominent.
```

---
---

# Phase 2 — Tool layer and chat

## P9 ★ — Tool framework
> Needs P1. Independent of ER — **can run in parallel with Phase 1.**

```
Build app/tools/base.py — the foundation every tool inherits. Read CLAUDE.md's
non-negotiable rules first; this module is where they're enforced.

- A Tool base class: Pydantic params model, a `principal` argument, an execute method
- Every tool returns {data, provenance: {sql_hash, row_ids, crime_nos}} — enforce this
  structurally so a tool physically cannot return bare data
- RBAC: a Principal model (role, unit_id, district_id, rank_hierarchy). Scope resolution
  using Unit.ParentUnit as a recursive CTE and Rank.Hierarchy. Roles per PLAN.md §6.
- k-anonymity: suppress any result cell with count < 5 for analyst and policymaker roles
- Audit log table + automatic logging of every call: principal, tool, params, row count,
  timestamp, and whether it was denied
- A registry that emits Anthropic tool-use JSON schemas from the Pydantic models

Acceptance: a demo tool works end-to-end, an out-of-scope principal is denied and the denial
is logged, and I can print the generated tool schemas.
```

## P9a — Data protection posture
> Extends P9. Closes PS1 §10's compliance bullet.

```
Add a governance layer to the tool framework, plus a GOVERNANCE.md documenting the posture.

In code:
- Data minimization: tools return only the columns their caller's role requires — an analyst
  querying trends should never receive names, even incidentally
- PII redaction helper applied at the serialization boundary, not per-tool, so it cannot be
  forgotten
- Retention and purpose-limitation fields on the audit log (why was this query run)
- Export controls: log every PDF export as an audit event with the principal and scope

In GOVERNANCE.md, map our controls to India's DPDP Act 2023 principles — purpose limitation,
data minimization, storage limitation, accountability — and note where a real deployment would
need more than a datathon prototype can provide. Do not overclaim compliance; describe the
posture and its limits honestly.
```

## P10 — Retrieval tools
> Needs P9 + P7.

```
Implement tools 1–6 from PLAN.md §3 in app/tools/retrieval.py: get_case, search_cases,
get_person, search_persons, get_case_timeline, get_chargesheet_status.

get_person must return the resolved profile across ALL linked FIRs via person_cluster, with
the confidence attached — never join on AccusedMasterID.

get_case_timeline returns the full date chain as ordered events:
incident → info received → registered → arrest(s) → chargesheet, with computed gaps.

Tests for each, including RBAC denial cases.
```

## P10a — Case summary
> Extends P10. Closes PS1 §6's "automated case summaries."

```
Implement the case_summary tool (tool 21 in PLAN.md §3).

Given a case_master_id, produce a structured summary: parties, acts and sections invoked,
the investigation timeline with computed gaps, arrest status, chargesheet status, linked
similar cases, and current risk flags. Structured fields, not prose — the LLM narrates it,
the tool does not write paragraphs.
```

## P11 — Compliance tools
> Needs P9. **Highest value-to-effort ratio in the project — your insurance if the ML slips.**

```
Implement chargesheet_deadline_watch and registration_delay_report from PLAN.md §4.1 and §4.6.

chargesheet_deadline_watch: find cases where an accused was arrested, no chargesheet exists,
and the gap is approaching the statutory 60/90-day default-bail window. Return them bucketed
by days remaining, sorted by urgency. Make the threshold configurable — heinous vs non-heinous
offences differ.

registration_delay_report: distribution of InfoReceivedPSDate → CrimeRegisteredDate lag by
unit, flagging statistical outliers.

Get this genuinely right.
```

## P12 — Network tools
> Needs P7 + P9.

```
Implement tools 7–10 in app/tools/network.py using networkx over person_cluster:
get_person_network (depth-limited), find_shortest_path, detect_communities (Louvain),
get_repeat_offenders.

detect_communities should flag groups spanning multiple police stations — cross-jurisdiction
groups are the interesting ones, since they're invisible to any single station.

Return node/edge structures ready for Cytoscape.js. Cache the graph build; don't rebuild per call.
```

## P13 — Trend and hotspot tools
> Needs P9.

```
Implement tools 11–15 in app/tools/trends.py: crime_trend, hotspot_scan (DBSCAN over
lat/long), spatiotemporal_clusters (time-of-day × location), compare_to_baseline (z-score vs
historical, this powers the red-zone alert), seasonality.

Every geo result must mark whether each point is a precise GPS coordinate or a district
centroid fallback — never blur that distinction, the map has to be honest about it.

Also add a zero_fir_flows tool: cross-jurisdiction case flow derived from the CrimeNo category
digit. Nobody else will think to extract this.
```

## P13a — Event calendar and anomaly detection
> Extends P13. Closes PS1 §3's "event-based" analysis and the anomaly-detection capability.

```
Two additions to the trends layer.

1. Event-based analysis. Build a Karnataka events calendar: major festivals (Dasara, Ganesh
   Chaturthi, Deepavali, Ugadi), election dates, major public gatherings, and harvest periods.
   Add an event_impact tool measuring crime deviation in windows around each event type,
   by district and crime head. Seasonality alone doesn't cover this.

2. Explicit anomaly detection. Make it a first-class tool: detect_anomalies(district?, window)
   surfacing incidents that deviate from established patterns — unusual crime type for the
   location, unusual timing, unusual victim/accused profile for that crime head, MO that
   doesn't match any known cluster. Return each with a plain-language reason it was flagged.

The unmatched-MO case is the investigatively interesting one: a crime whose method resembles
nothing else in the database is either genuinely novel or wrongly classified. Both are worth
an investigator's attention.
```

## P14 ★ — Orchestration loop
> Needs P10–P13. **The demo spine.**

```
Build app/api/ — FastAPI plus the Claude tool-calling loop.

- POST /chat with conversation history and a principal; runs the tool-calling loop against the
  registry from P9
- System prompt enforcing CLAUDE.md's rules: never author a fact, only narrate tool results,
  and when no tool can answer, say so plainly instead of estimating
- Multi-turn context so follow-ups work without repeating context ("and in Mysuru?" after a
  Bengaluru question must resolve correctly)
- The response carries the full provenance chain: which tools ran, with what params, returning
  which CrimeNos
- Stream responses

Write an eval set of ~30 questions covering each tool plus several deliberately unanswerable
ones. The unanswerable cases must produce a refusal, not a guess — treat any fabricated answer
as a failing test.

Acceptance: the eval suite runs and reports pass rate. Show me a transcript for one multi-turn
conversation.
```

---
---

# Phase 3 — Intelligence layer

## P15 ★ — MO fingerprinting
> Needs P4 (`BriefFacts_en`). There is no MO field in the schema — you're creating one.

```
Build ml/mo/.

- Embed BriefFacts_en (multilingual embedding model), store in pgvector
- Cluster with HDBSCAN, tuned so clusters are interpretable rather than merely numerous
- Label each cluster with claude-sonnet-5: a short MO name plus the distinguishing features
- Expose get_mo_cluster and find_similar_cases as tools

find_similar_cases must return each similar case WITH its cstype outcome — "here are 12
similar cases, 8 were chargesheeted, and here's what the investigators did" is the useful
answer, not bare similarity.

Acceptance: show me the cluster labels and 5 sample cases each. I need to eyeball whether the
clusters are real, so print the English text.
```

## P16 — Undetected-case risk model
> Needs P3. `cstype` is your only supervised label — treat it as precious.

```
Build ml/risk/undetected.py. ChargesheetDetails.cstype is our only supervised label: A =
chargesheet, B = false case, C = undetected.

Train gradient boosting to predict P(cstype = C) on open cases. Features: crime head, gravity,
reporting delay, registration delay, has_arrest, #accused, #victims, station caseload, IO
caseload, MO cluster.

- Temporal train/test split, not random — we predict forward in time
- Report AUC and a calibration curve
- SHAP or equivalent per-case factor breakdown, because the tool must explain WHY a case is
  flagged
- Expose as the undetected_risk tool

This targets police resource allocation, not people. Keep it that way — no person-level
features about the accused beyond case counts.
```

## P17 — Offender risk and investigative leads
> Needs P15 + P12.

```
Implement offender_risk_score and investigative_leads.

offender_risk_score: scored from resolved case history — frequency, recency, escalation in
gravity over time, MO consistency, network centrality. Return a factor breakdown, never a bare
number. This prioritizes EXISTING open investigations only; it is not a prediction that anyone
will offend, and the tool description must say so.

investigative_leads(case_master_id): combine similar solved cases, offenders with a matching MO
cluster active in the geographic area, and network paths from any known accused. Return ranked
leads, each with its supporting evidence.
```

## P17a ★ — Proactive alert engine
> Needs P11, P12, P13, P15. **Closes PS1 §8 and the "proactive prevention" framing. Higher
> priority than P18** — an early-warning system that waits to be asked is not one.

```
Build app/alerts/ — a scheduled alerting subsystem.

Alert rules, each evaluated on a schedule:
- Crime spike: compare_to_baseline crosses a z-score threshold for a district × crime head
- Emerging MO cluster: a new MO cluster growing faster than a threshold
- Gang activity: a detected community's case rate rising, or one expanding into a new station
- Near-repeat window: a burglary/theft opens an elevated-risk window in a radius
- Chargesheet deadline: cases entering the danger band (reuse P11)
- Repeat offender resurfacing: a person with a prior record appearing in a new FIR

Requirements:
- An alerts table with severity, evidence (the tool calls that produced it), and status
  (new/acknowledged/dismissed)
- Routed by RBAC scope — an SHO gets their station's alerts, SP gets the district's
- An alert inbox in the UI with acknowledge/dismiss, and a badge in the chat header
- Clicking an alert opens the supporting evidence and drops the context into chat, so an
  investigator can immediately ask follow-up questions about it
- Runs on APScheduler or a cron endpoint — no extra infrastructure

Acceptance: run the evaluator over the demo data and show me alerts generated with their
evidence chains.
```

## P18 — Hotspot forecasting
> Needs P13. Cuttable if time runs short.

```
Build ml/forecast/. Predict crime counts by district × crime head × month, and near-repeat
risk windows (elevated risk in a radius after an incident — well established for burglary).

Benchmark honestly against a seasonal-naive baseline and report both numbers. A modest
documented lift is worth more than an unbenchmarked claim.

Places, times, and crime types only. No individual-level prediction anywhere in this module.
```

---
---

# Phase 4 — Interface

## P19 ★ — Frontend shell
> Needs P14.

```
Build web/ — React + Vite + TypeScript.

Four linked panes: chat (left), and a right side that switches between map, network graph, and
evidence. The key interaction: asking a question in chat updates the visual panes. That linkage
is what makes this feel like one product instead of two projects stapled together.

- Streaming chat
- An evidence drawer showing the provenance chain, where every CrimeNo is clickable and opens
  the case
- A role switcher for demoing RBAC (SHO / DySP / SP / SCRB Analyst / Policymaker)

Dark, dense, operational. This is a police tool, not a consumer app.
```

## P20 — Map and network panes
> Needs P19 + P12 + P13.

```
Map pane: MapLibre + deck.gl. Karnataka district boundaries, case points, hotspot heatmap,
district drill-down to police station. Precise GPS points and district-centroid fallbacks must
be visually distinct — never let an inferred point look precise.

Add the red-zone indicator: districts where compare_to_baseline shows a significant spike get a
pulsing highlight.

Network pane: Cytoscape.js. Nodes coloured by role (accused/victim/complainant), edges by
relationship type, communities visually grouped. Clicking a node loads that person into chat
context.
```

## P19b — Reasoning path visualization
> Needs P20 (reuses its Cytoscape setup). Closes PS1 §9's second bullet, which asks specifically
> for *visualization* of reasoning paths — a provenance list doesn't satisfy it.

```
Build a reasoning-path visualization in the evidence pane.

Render each answer's derivation as a node diagram, not a list:

  question → [tool: search_cases] → 1,204 rows
           → [tool: detect_communities] → 3 groups
           → [tool: get_person] → 8 people
           → conclusion, with the CrimeNos that support it

- Nodes are tool invocations, edges are data flow, leaf nodes are the source records
- Clicking any node shows its exact parameters and the rows it returned
- Where a claim rests on a correlation or statistical test, show the underlying scatter or
  distribution inline rather than just the coefficient
- Any step where the model chose between tools should show what it chose and what it passed over

Reuse the Cytoscape setup from P20. Build it so it can be shown on stage without narration.
```

## P19a — SCRB strategic dashboard
> Needs P4a + P17a + P19. Closes the policymaker/analyst persona, who won't use chat.

```
Build a dashboard landing view for the SCRB Analyst and Policymaker roles.

- State-level KPI row: total cases, detection rate (cstype A share), false-case rate, average
  time-to-chargesheet, cases pending past the statutory window
- Karnataka choropleth by crime rate per 100k, switchable by crime head
- Top movers: districts with the largest deviation from their own baseline
- Socio-economic correlation panel from P4a
- The alert feed from P17a
- Everything k-anonymity suppressed and aggregate-only for these roles, and every tile
  clickable through to the chat interface pre-loaded with the corresponding question

The tiles must be driven by the same tools as chat — no separate query path, or the numbers
will drift apart and you'll get caught on stage.
```

## P21 — ER review queue
> Needs P7 + P19. Cuttable — the backend queue matters more than the UI.

```
Build the human-in-the-loop review UI for the 0.60–0.85 confidence band from P7.

Side-by-side record comparison, the signal breakdown showing why they scored where they did,
and merge / reject / defer actions. Decisions persist and feed back as labelled training data.

This UI is worth showing in the demo — it's concrete proof that we treat identity resolution as
a decision requiring human judgment rather than something we silently guess at.
```

---
---

# Phase 5 — Language and export

## P22 — Kannada template system
> Needs P19. **Find your Kannada validator before this lands, not after.**

```
Build the Kannada layer per PLAN.md §8. Critical constraint: our team does not read Kannada,
so output must be VERIFIABLE — template-based only, never free-form generation.

- Extract every user-facing response pattern into ~40 parameterized templates in
  web/src/i18n/, with English and Kannada versions side by side
- Templates take structured data slots (district, count, year, crime type) — the same tool
  results that drive the English response
- A language toggle
- Generate a single reviewer-friendly page listing all 40 templates with sample data filled
  in, English beside Kannada, for a native speaker to validate in one sitting

Acceptance: the review page renders, and no user-facing Kannada string exists outside the
template file.
```

## P23 — Voice
> Needs P22. First to cut if time runs short.

```
Integrate Bhashini (MeitY) for Kannada + English ASR and TTS.

- Push-to-talk in the chat pane, ASR → the existing chat endpoint
- TTS over the template-rendered response
- Graceful degradation: if Bhashini is unreachable, fall back to text and say so visibly.
  Never fail silently during a demo.

Keep the integration behind an interface so we can swap providers if Bhashini is slow on the
day.
```

## P24 — PDF export
> Needs P14 + P22.

```
Conversation export to PDF via WeasyPrint. Must include the full provenance trail — every
claim with its supporting CrimeNos — plus a header with the principal, timestamp, and role, so
the export is itself an auditable record. Support both English and Kannada. Save locally.
```

---
---

# Phase 6 — Demo

## P25 — Demo preparation
> Do not skip. A working system that breaks on stage scores like a broken system.

```
Read the demo script in PLAN.md §10.

- A seeded demo dataset where every beat lands: a resolvable repeat offender with messy name
  variants, a genuine cross-station community, an MO cluster with unsolved matches, and cases
  sitting at day 75+ without a chargesheet
- A reset command that restores demo state in under 30 seconds
- Health checks for every external dependency
- Verify each beat in order and tell me which ones are fragile

Then walk the whole script end to end and report exactly where it breaks.
```

---
---

# If you fall behind

Cut in this order. **Do not cut upward past the line.**

1. P23 voice — keep the Kannada templates and text
2. P18 forecasting — P17a already covers the early-warning requirement
3. P21 review queue UI — keep the backend queue and show it via API
4. P19b reasoning viz — the evidence drawer partially covers §9
5. P20 network pane polish

**Never cut:** P5–P8 (entity resolution), P9 (tool framework), P11 (chargesheet board),
P14 (orchestration), P25 (demo prep).

That set alone — a measured ER engine, a citable non-hallucinating chat interface, one
immediately useful operational feature, and a demo that survives contact with the stage — is a
stronger submission than most of what will be in the room.

## Parallelization for two developers

The dependency chain is mostly linear, but three splits work cleanly:

| While one person does… | The other can do… |
|---|---|
| P5 → P6 → P7 → P8 (entity resolution) | P4a, then P9 → P9a → P11 → P13 → P13a |
| P15 → P16 → P17 (intelligence) | P19 → P20 (interface shell) |
| P17a → P19a (alerts + dashboard) | P22 → P23 → P24 (language + export) |

P14 is the merge point — it needs the tools from one track and gates the frontend on the other.
Plan to converge there, and claim it on the board so you don't both start it.
