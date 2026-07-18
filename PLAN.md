# KSP Crime Intelligence Platform — Build Plan

**Problem Statement 1** — Intelligent Conversational AI & Crime Analytics Platform
Karnataka State Police / SCRB · Datathon 2026

---

## 0. The one-sentence pitch

> The criminal network already exists inside KSP's records. It is invisible only because
> the same person is written a dozen different ways across a dozen police stations, and
> because the database has no concept of a person at all.

Everything in this plan follows from that. `Accused.AccusedMasterID` is a **row ID scoped
to one FIR**, not a person ID. There is no table anywhere in the supplied schema that says
"these two FIRs involve the same human being." Until you build that, every network,
repeat-offender, gang, and risk feature in the problem statement is uncomputable.

---

## 1. Architecture

```
┌─ Ingest ─────────────────────────────────────────────────────────┐
│  Raw KSP schema (as supplied)                                    │
│  + CrimeNo parsing (category|district|station|year|serial)       │
│  + BriefFacts language detect → BriefFacts_en (parallel column)  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Entity Resolution ──────────────────────────────────────────────┐
│  person_cluster  ← the table KSP doesn't have                    │
│  name parse → normalize → block → score → collective boost       │
│  → cluster + confidence + merge evidence + review queue          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Derived layer ──────────────────────────────────────────────────┐
│  co-offending graph · MO clusters (pgvector) · case timelines     │
│  · risk scores · hotspot grids                                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Tool layer  (~25 typed, parameterized, RBAC-checked functions) ─┐
│  every call → audit log + provenance {sql_hash, row_ids, crime_nos}│
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Orchestration ──────────────────────────────────────────────────┐
│  Claude tool-calling loop. The model NEVER writes SQL and NEVER   │
│  states a fact not present in a tool result.                      │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ Surfaces ───────────────────────────────────────────────────────┐
│  Chat │ Map │ Network graph │ Evidence drawer │ PDF │ Kannada voice│
└──────────────────────────────────────────────────────────────────┘
```

### Stack decisions (and why)

| Layer | Choice | Reason |
|---|---|---|
| DB | Postgres 16 + PostGIS + pgvector | One service covers relational, geo, and vector |
| Graph | **networkx in-memory**, not Neo4j | At datathon scale this is fine, renders identically, saves a day of setup and sync. Fall back to Apache AGE only if data > ~2M rows |
| API | FastAPI + Pydantic | Tool params become schemas for free |
| LLM | `claude-opus-4-8` for orchestration; `claude-sonnet-5` for bulk jobs (translation, MO labelling) | Cost split |
| Frontend | React + Vite, MapLibre/deck.gl, Cytoscape.js | Chat pane and visual panes linked |
| Language | Bhashini (MeitY) for ASR/TTS | Government's own stack — what a real deployment would use |
| PDF | WeasyPrint | HTML → PDF, keeps citation formatting |

**Non-negotiable rule:** the LLM selects tools and narrates results. It does not author
facts. This single constraint delivers §9 (explainability), §10 (RBAC + audit), and
demo reliability all at once.

---

## 2. Entity Resolution — the core engine

You have only: name string, `AgeYear`, `GenderID`, and context. No father's name field, no
address, no phone, no DOB. So matching must be **relational**, not attribute-based.

### Stage 1 — Name parsing
`AccusedName` is free text and in Indian FIRs it carries structure inside it:

```
"Ramesh @ Rami S/o Krishnappa"
  → given: Ramesh
  → alias: Rami                 ← the "@" convention
  → patronymic: Krishnappa      ← S/o, D/o, W/o, C/o
```
Extracting the patronymic back out gives you a **second matching key for free**. Aliases
give you a third. Build this with rules + regex, then iterate against real data.

### Stage 2 — Normalization
- Kannada → Roman transliteration (AI4Bharat IndicXlit or `indic-transliteration`)
- Case-fold, strip honorifics and punctuation
- Kannada terminal-vowel variants: `Ramesh / Ramesha / Rameshu`, `-appa / -anna / -amma`
- Phonetic key: Double Metaphone over the transliteration, **plus** a Dravidian rule set
  (collapse aspirates, `th↔t`, `dh↔d`, `sh↔s`, `v↔w`, retroflex↔dental).
  Plain Soundex is tuned for English surnames and will fail here.

### Stage 3 — Blocking
Never compare all pairs. Candidate blocks: phonetic key of first token · district ·
shared arrest event. This is what keeps it tractable.

### Stage 4 — Pairwise scoring
| Signal | Weight |
|---|---|
| Jaro-Winkler on normalized name | high |
| Patronymic match (when both present) | very high |
| Alias overlap | very high |
| Age consistency — estimate birth year from `AgeYear` + `CrimeRegisteredDate`, require ±2y | high |
| Gender match | hard gate |
| Same `PoliceStationID` / `DistrictID` / adjacent district | medium |

### Stage 5 — Collective boost (the novel part)
Build the co-arrest graph from `inv_arrestsurrenderaccused`. If two candidate records share
an already-resolved co-offender, boost the score. Then **iterate**: resolve → propagate
through the graph → re-resolve, 2–3 rounds.

This is *collective entity resolution* — identities and the network are solved jointly,
each improving the other. It is the technically correct approach given these fields, and
it is the strongest engineering story you have.

### Stage 6 — Clustering & review
- score ≥ 0.85 → auto-merge
- 0.60–0.85 → **human review queue in the UI** (never auto-merge this band)
- Persist `person_cluster_id`, confidence, and the merge evidence for every link

### Stage 7 — Evaluation
Generate synthetic data with **known** ground-truth identities and deliberately injected
name variants. Report pairwise precision / recall / F1. A concrete number on a slide beats
any amount of description.

---

## 3. Tool catalog (~25 functions)

Every tool: typed Pydantic params · parameterized SQL only · takes a `principal` and
filters by role · returns `{data, provenance: {sql_hash, row_ids, crime_nos}}` · logs to audit.

**Retrieval**
1. `get_case(crime_no | case_master_id)`
2. `search_cases(district, station, date_range, crime_head, status, gravity, act_section)`
3. `get_person(person_cluster_id)` → resolved profile + every linked FIR
4. `search_persons(name, age, gender, district)` → candidates with confidence
5. `get_case_timeline(case_master_id)` → the full date chain
6. `get_chargesheet_status(case_master_id)`

**Network**
7. `get_person_network(person_cluster_id, depth)`
8. `find_shortest_path(person_a, person_b)`
9. `detect_communities(district?, crime_head?)` → Louvain → gang candidates
10. `get_repeat_offenders(district?, min_cases, window)`

**Pattern & trend**
11. `crime_trend(group_by, filters)`
12. `hotspot_scan(area, crime_head, date_range)` → DBSCAN over lat/long
13. `spatiotemporal_clusters(...)` → time-of-day × location
14. `compare_to_baseline(district, crime_head, period)` → z-score vs history → the "red zone" alert
15. `seasonality(crime_head, district)` → monthly / festival effects

**Sociological** *(complainant-side only — see §5)*
16. `complainant_demographics(filters, breakdown)`
17. `victimization_profile(crime_head, district)`

**Criminological / MO**
18. `get_mo_cluster(case_master_id)`
19. `find_similar_cases(case_master_id, k)` → vector search over `BriefFacts_en`, returned **with outcomes**
20. `offender_risk_score(person_cluster_id)` → score + factor breakdown

**Decision support**
21. `case_summary(case_master_id)`
22. `investigative_leads(case_master_id)`
23. `undetected_risk(case_master_id)` → P(`cstype` = C)

**Compliance & governance**
24. `chargesheet_deadline_watch(unit_id | district)`
25. `registration_delay_report(unit_id)`
26. `audit_log_query(...)` — supervisor and above only

---

## 4. The features that win, ranked by value ÷ effort

### 4.1 Chargesheet deadline board ★ highest ratio in the project
From the date chain: arrest → chargesheet. If an accused is in custody and no chargesheet
is filed within the statutory 60/90-day window (CrPC §167, now the BNSS equivalent), the
accused becomes entitled to **default bail**.

> "43 cases across this district are at day 75+ with an arrest and no chargesheet."

Pure SQL over `ArrestSurrender.ArrestSurrenderDate` and `ChargesheetDetails.csdate`. One
afternoon of work, and it is immediately operationally useful to a real officer. Build it
early — it is your insurance policy if the ML slips.

### 4.2 Undetected-case risk model ★ best ML target in the schema
`ChargesheetDetails.cstype` gives labels on every closed case: `A` chargesheet, `B` false
case, `C` undetected. Train gradient boosting to predict `P(C)` on open cases.

Features: crime head, gravity, reporting delay, registration delay, has_arrest, #accused,
#victims, station caseload, IO caseload, MO cluster.

This targets **police resource allocation, not people** — it sidesteps every
predictive-policing ethics objection. Report AUC.

Also from `cstype`: false-case rate by station (`B`) and detection-rate benchmarking
adjusted for crime mix. SCRB will care about both.

### 4.3 MO fingerprinting → investigative leads
There is **no modus operandi field anywhere** in the schema. `BriefFacts` is the only
unstructured text. So MO must be derived: embed `BriefFacts_en` → HDBSCAN → have an LLM
label each cluster. You are creating a field KSP does not have.

Then match unsolved cases against MO signatures of solved ones. The output is not a chart:

> "14 unsolved chain-snatchings across Bengaluru South, Ramanagara and Mandya share MO
> cluster #7. Two convicted offenders with this MO were released within 40 km in February.
> FIRs: [list]."

Judges remember leads. They do not remember heatmaps.

### 4.4 Network + community detection
Only possible after ER. Louvain over the co-offending graph → organized-group candidates
spanning multiple police stations. Render with Cytoscape, driven from chat.

### 4.5 Zero FIR cross-jurisdiction analysis
`CrimeNo` category digit `8` = Zero FIR — a case registered outside the jurisdiction where
it occurred. Almost nobody will think to extract this. Cross-jurisdiction crime flow between
districts is a novel, cheap analytic.

### 4.6 Registration-delay integrity metric
Persistent lag between `InfoReceivedPSDate` and `CrimeRegisteredDate` is the statistical
signature of delayed or refused FIR registration. Frame as station-level quality assurance.

---

## 5. Scope boundaries — state these openly

| PS1 section | Support in schema | Your move |
|---|---|---|
| 1. Conversational interface | Full | Build |
| 2. Network analysis | **Only after ER** | Build (gated on §2 of this plan) |
| 3. Patterns & trends | Full | Build |
| 4. Sociological insights | **Partial** | See below |
| 5. Offender profiling | Only after ER + derived MO | Build |
| 6. Investigator support | Good | Build |
| 7. **Financial crime** | **None** | Stub + declare |
| 8. Forecasting | Good | Build, place/time/type only |
| 9. Explainable AI | Full | Comes free from architecture |
| 10. RBAC & audit | Full | Build |

**On §4:** caste, religion and occupation exist **only** on `ComplainantDetails` — not on
`Accused`, not on `Victim`. You therefore cannot demographically profile offenders. Make
this a stance, not an apology: *do the sociology of victimization, not of offenders.* Who
reports crime, who doesn't, which communities under-report relative to population — that is
defensible criminology. Offender profiling by caste or religion is indefensible, and the
schema conveniently makes it impossible. Say so on stage.

**On §7:** there is no account, transaction, property, phone, or vehicle data anywhere in
this schema. **Do not fake it.** Present it as a designed integration point (ICJS / bank
feeds / CDR) with the interfaces stubbed, and state plainly that the source data is out of
scope. Judges who know this schema will notice anyone pretending otherwise, and the honesty
buys credibility for everything else you claim.

---

## 6. Security, RBAC & governance (§10) — nearly free from the schema

`Unit.ParentUnit` is a self-referencing hierarchy. `Rank.Hierarchy` is an ordered level.
Together they give you the access model directly:

| Role | Scope | Person-level data? |
|---|---|---|
| SHO / Constable | own `UnitID` | yes |
| DySP | `ParentUnit` subtree | yes |
| SP | district | yes |
| SCRB Analyst | state | **aggregates only** |
| Policymaker | state | **aggregates only**, person tools disabled |

Enforce at the **tool boundary**, never in the prompt. Add **k-anonymity suppression**:
blank any cell with count < 5 for analyst and policymaker roles. That is real governance
practice and costs ten lines.

Audit log: principal, tool, params, row count, timestamp — every call. The tool-call trace
*is* the audit trail, so §9 and §10 are the same artifact.

---

## 7. ML models — exactly three, all defensible

1. **MO clustering** — multilingual embeddings over `BriefFacts_en` → HDBSCAN → LLM labels
2. **Undetected-case risk** — gradient boosting → `P(cstype = C)`, report AUC
3. **Hotspot forecast** — near-repeat / KDE + seasonality, benchmarked against a
   seasonal-naive baseline (report both; honesty about a modest lift beats an unbenchmarked claim)

**Explicitly NOT built:** individual-level crime prediction. Put one slide on bias, feedback
loops in patrol allocation, and why you constrained the model. Turning your biggest ethical
exposure into a deliberate design stance reads as maturity.

---

## 8. Kannada strategy (team has no Kannada speaker)

The risk is not translation — models handle that. The risk is **unverifiable output**.

Because the LLM never generates facts, your Kannada surface is not free-form text. It is
roughly **40 fixed sentence templates with data slots**:

```
"{district} ನಲ್ಲಿ {year} ರಲ್ಲಿ {count} ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ."
```

Forty templates is **one Kannada speaker, one afternoon, validated forever**. You don't need
one on the team — you need two hours from one. At a datathon in Karnataka that person is
findable: another participant, an on-site mentor, a friend.

Three moves:
1. **`BriefFacts_en` at ingest, day one.** Keep the original, add a translated column.
   Everything downstream — clustering, debugging, checking whether MO clusters are
   sensible — then happens in a language you can read. This removes your biggest hidden risk.
2. **Bhashini** for ASR/TTS. Choosing the government's own language stack over a US cloud
   vendor is a procurement-aware signal to a government panel.
3. **Transliteration, not fluency**, for names. IndicXlit. No Kannada literacy required.

**Hard rule:** never demo a Kannada voice path no human has verified. If the templates are
still unreviewed in the final week, cut to validated Kannada *display* only, drop voice
output, and say so. A working English demo with an honest gap beats a Kannada demo that says
something wrong in front of a panel that reads Kannada.

---

## 9. Phase plan

Adjust to your actual deadline; the ordering matters more than the dates.

| Phase | Work | Output |
|---|---|---|
| **0 · Days 1–2** | Data recon. Send §11 questions to organizers. Build synthetic FIR generator with known identities + injected name variants. | You can build before real data lands |
| **1 · Days 3–7** | Ingest, `CrimeNo` parsing, `BriefFacts_en`, **entity resolution + F1 metric** | `person_cluster` exists. This is the milestone everything waits on. |
| **2 · Week 2** | Tool layer, RBAC, audit, chat orchestration, evidence drawer, **chargesheet deadline board** | Demoable end-to-end |
| **3 · Week 2–3** | MO clustering, similar-case retrieval, undetected-risk model, community detection | The intelligence layer |
| **4 · Week 3** | UI: linked chat / map / graph panes, review queue | Looks like a product |
| **5 · Week 3–4** | Kannada templates + Bhashini voice + PDF export | The judge-facing polish |
| **6 · Final** | Demo script, seed data, rehearse, failure fallbacks | |

### 🔻 Minimum viable submission cut line
**Phases 0–2, plus the chargesheet board, plus one working map.**
That alone — a real entity-resolution engine, a citable non-hallucinating chat interface,
and one immediately useful operational feature — beats most of the field. Everything after
is upside. Protect this line; do not let it slip for a fancier model.

### Team split (4 people)
- **A — Data + ER.** Your strongest engineer. Everything blocks on this.
- **B — Tool layer, API, RBAC, audit, orchestration.**
- **C — ML: MO clustering, risk model, forecasting.**
- **D — Frontend, Kannada, PDF, demo production.**

---

## 10. Demo script (7 minutes)

| Time | Beat |
|---|---|
| 0:30 | Show the raw `Accused` table. "`AccusedMasterID` is per-FIR. This database has no concept of a person. That's why nothing is connected." |
| 1:30 | Kannada voice query from a station constable → spoken answer → PDF saved |
| 2:30 | "Show repeat offenders for chain-snatching in Bengaluru South" → resolved persons with confidence scores → open the evidence drawer |
| 4:00 | Click a person → network graph → community detection surfaces a group operating across three stations |
| 5:00 | MO cluster → 14 unsolved cases match → concrete investigative lead |
| 6:00 | Chargesheet deadline board: 43 cases at day 75+ |
| 6:30 | **Ask something the data cannot answer.** System replies "I cannot answer this from the available records." Then show the audit log. |

That last beat is the winner. Every other team's system will confidently make something up.

---

## 11. Questions to send the organizers — day one

Real defects and gaps in the supplied ER diagram:

1. **Type mismatch.** `ActSectionAssociation.ActID INT → Act.ActCode VARCHAR`, and
   `SectionID INT → Section.SectionCode VARCHAR`. But `CrimeHeadActSection.ActCode` is
   correctly VARCHAR. Which is authoritative?
2. **Two tables referenced but never defined:** `Inv_OccuranceTime` (1:1 with CaseMaster)
   and `inv_arrestsurrenderaccused` — the junction table ER depends on. Need its columns.
3. **Ambiguous arrest→accused link.** `ArrestSurrender` has a direct `AccusedMasterID` FK
   *and* the junction table. Which one is real?
4. **Location duplication.** `CaseMaster.latitude/longitude` vs `Inv_OccuranceTime`'s
   "occurrence time/location record."
5. **`Section` has no declared primary key.**
6. **Null rate on `latitude`/`longitude`?** Expect heavy nulls. Plan the fallback to
   `Unit → District` centroid, and make the map visually honest about precise vs. inferred points.
7. Data volume, date range, real vs. synthetic, and the PII handling policy.

---

## 12. Principles to hold onto

- **Solve identity first.** Every impressive feature is downstream of it.
- **The model never authors a fact.** Tools return data; the model narrates.
- **Every claim clicks through to a `CrimeNo`.**
- **Predict places, times, and case outcomes — never people.**
- **Name the gaps out loud.** §7 has no data. Say so. Credibility compounds.
