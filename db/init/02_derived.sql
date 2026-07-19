-- =============================================================================
-- DERIVED SCHEMA — everything this project computes.
--
-- Safe to DROP and rebuild from ksp at any time. Nothing here is source data.
--
-- P1 creates only the entity-resolution core (person_cluster,
-- person_cluster_member) plus the translation table that P4 fills. Later
-- prompts add their own tables to this schema:
--   P4   → case_translation (created here so ingest has a target)
--   P7   → er_review_queue (created here; P21 builds the UI over it)
--   P9   → audit_log
--   P15  → mo_cluster, case_mo_assignment
--   P17a → alert, alert_rule
-- =============================================================================

SET search_path TO derived, ksp, public;

-- -----------------------------------------------------------------------------
-- Entity resolution — the table the KSP schema does not have
-- -----------------------------------------------------------------------------

CREATE TABLE person_cluster (
    person_cluster_id BIGSERIAL PRIMARY KEY,
    display_name      VARCHAR(300),
    canonical_given   VARCHAR(160),
    canonical_patronymic VARCHAR(160),
    phonetic_key      VARCHAR(80),
    est_birth_year    INTEGER,
    gender_id         INTEGER REFERENCES ksp.gender_master(gender_id),
    member_count      INTEGER NOT NULL DEFAULT 0,
    confidence        NUMERIC(4, 3),
    resolved_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    resolver_version  VARCHAR(40)
);
COMMENT ON TABLE person_cluster IS
  'One row per RESOLVED HUMAN BEING. This is the central contribution of the project: '
  'the KSP schema has no person entity, so every cross-case question about people is '
  'answered through this table. Built by er/resolve.py (P7).';
COMMENT ON COLUMN person_cluster.confidence IS
  'Aggregate confidence of the cluster. >=0.85 auto-merged; 0.60-0.85 routed to '
  'er_review_queue and never auto-merged.';
COMMENT ON COLUMN person_cluster.resolver_version IS
  'Which version of the resolver produced this. Lets us re-run and compare without '
  'losing the previous result.';
CREATE INDEX idx_person_cluster_phonetic ON person_cluster(phonetic_key);
CREATE INDEX idx_person_cluster_name_trgm ON person_cluster USING GIN (display_name gin_trgm_ops);

-- Roles a resolved person can hold in a case. Deliberately a single namespace:
-- the same person_cluster_id may appear as accused in one FIR and victim in
-- another. That overlap is the point (P7a) — do not split this into per-role
-- cluster tables.
CREATE TYPE party_role AS ENUM ('accused', 'victim', 'complainant');

CREATE TABLE person_cluster_member (
    member_id         BIGSERIAL PRIMARY KEY,
    person_cluster_id BIGINT NOT NULL REFERENCES person_cluster(person_cluster_id) ON DELETE CASCADE,
    role              party_role NOT NULL,
    source_row_id     INTEGER NOT NULL,
    case_master_id    INTEGER NOT NULL REFERENCES ksp.case_master(case_master_id) ON DELETE CASCADE,
    raw_name          VARCHAR(300),
    parsed_given      VARCHAR(160),
    parsed_alias      VARCHAR(160),
    parsed_patronymic VARCHAR(160),
    parsed_relation   VARCHAR(10),
    age_year          INTEGER,
    match_confidence  NUMERIC(4, 3),
    match_evidence    JSONB,
    CONSTRAINT uq_pcm_source UNIQUE (role, source_row_id)
);
COMMENT ON TABLE person_cluster_member IS
  'Links each party row in the KSP schema to its resolved person. source_row_id points at '
  'accused.accused_master_id, victim.victim_master_id or complainant_details.complainant_id '
  'depending on role.';
COMMENT ON COLUMN person_cluster_member.match_evidence IS
  'Which signals fired and with what contribution — name similarity, patronymic match, '
  'age consistency, shared co-offender, geography. This is what answers "why do you think '
  'these are the same person" and it feeds the explainability requirement (PS1 §9). '
  'Never leave this null on a merge.';
COMMENT ON COLUMN person_cluster_member.parsed_relation IS 'S/o, D/o, W/o, C/o';
CREATE INDEX idx_pcm_cluster ON person_cluster_member(person_cluster_id);
CREATE INDEX idx_pcm_case ON person_cluster_member(case_master_id);
CREATE INDEX idx_pcm_role ON person_cluster_member(role);

-- P7 writes here; P21 builds the review UI over it.
CREATE TABLE er_review_queue (
    review_id        BIGSERIAL PRIMARY KEY,
    role_a           party_role NOT NULL,
    source_row_id_a  INTEGER NOT NULL,
    role_b           party_role NOT NULL,
    source_row_id_b  INTEGER NOT NULL,
    score            NUMERIC(4, 3) NOT NULL,
    signals          JSONB NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    decided_by       VARCHAR(120),
    decided_at       TIMESTAMP,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_review_status CHECK (status IN ('pending', 'merged', 'rejected', 'deferred'))
);
COMMENT ON TABLE er_review_queue IS
  'Candidate pairs scoring 0.60-0.85 — the band where the resolver is unsure and a human '
  'decides. These are NEVER auto-merged. Decisions become labelled training data.';
CREATE INDEX idx_review_status ON er_review_queue(status);

-- -----------------------------------------------------------------------------
-- Translation (P4 fills this)
-- -----------------------------------------------------------------------------

CREATE TABLE case_translation (
    case_master_id  INTEGER PRIMARY KEY REFERENCES ksp.case_master(case_master_id) ON DELETE CASCADE,
    detected_lang   VARCHAR(20),
    brief_facts_en  TEXT,
    translated_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    model           VARCHAR(60)
);
COMMENT ON TABLE case_translation IS
  'English rendering of ksp.case_master.brief_facts. Kept OUT of the ksp schema so the '
  'source stays untouched. All downstream analysis and debugging reads brief_facts_en — '
  'the team does not read Kannada. Filled by ingest/translate.py (P4).';
CREATE INDEX idx_translation_lang ON case_translation(detected_lang);

-- -----------------------------------------------------------------------------
-- Audit log (P9). Every tool call is logged here — allowed or denied. The tool-call
-- trace IS the audit trail, so this table satisfies both §9 (explainability) and §10
-- (accountability): who asked what, with which parameters, in what scope, and whether
-- the tool boundary let it through.
-- -----------------------------------------------------------------------------

CREATE TABLE audit_log (
    audit_id         BIGSERIAL PRIMARY KEY,
    ts               TIMESTAMP NOT NULL DEFAULT NOW(),
    principal_name   VARCHAR(120),
    principal_role   VARCHAR(40) NOT NULL,
    principal_unit   INTEGER,
    principal_district INTEGER,
    tool             VARCHAR(80) NOT NULL,
    params           JSONB,
    row_count        INTEGER NOT NULL DEFAULT 0,
    denied           BOOLEAN NOT NULL DEFAULT FALSE,
    denial_reason    VARCHAR(300)
);
COMMENT ON TABLE audit_log IS
  'One row per tool invocation (P9). principal_role/unit/district capture who called; '
  'params is the validated tool input; denied + denial_reason record RBAC rejections. '
  'This is the evidence trail — never truncate it in production.';
CREATE INDEX idx_audit_ts ON audit_log(ts);
CREATE INDEX idx_audit_tool ON audit_log(tool);
CREATE INDEX idx_audit_denied ON audit_log(denied) WHERE denied;

-- -----------------------------------------------------------------------------
-- MO fingerprinting (P15) — the modus-operandi layer the KSP schema lacks.
-- There is no MO field; it is derived by clustering BriefFacts free text. Each
-- case gets an embedding (pgvector) and a cluster; each cluster carries a label
-- and its outcome (cstype) mix so find_similar_cases can answer "12 similar
-- cases, 8 chargesheeted" rather than bare similarity.
-- -----------------------------------------------------------------------------

CREATE TABLE mo_cluster (
    mo_cluster_id   INTEGER PRIMARY KEY,
    label           VARCHAR(200) NOT NULL,
    top_terms       TEXT[] NOT NULL DEFAULT '{}',
    size            INTEGER NOT NULL,
    cstype_a        INTEGER NOT NULL DEFAULT 0,   -- chargesheeted
    cstype_b        INTEGER NOT NULL DEFAULT 0,   -- false case
    cstype_c        INTEGER NOT NULL DEFAULT 0,   -- undetected
    cstype_open     INTEGER NOT NULL DEFAULT 0    -- no chargesheet row yet
);
COMMENT ON TABLE mo_cluster IS
  'Derived modus-operandi clusters (P15). label + top_terms describe the pattern; '
  'the cstype_* columns are the outcome mix that makes similar-case lookup actionable.';

CREATE TABLE case_mo_assignment (
    case_master_id  INTEGER PRIMARY KEY,
    mo_cluster_id   INTEGER REFERENCES mo_cluster(mo_cluster_id),  -- NULL = noise/unclustered
    embedding       vector(128) NOT NULL
);
CREATE INDEX idx_case_mo_cluster ON case_mo_assignment(mo_cluster_id);
CREATE INDEX idx_case_mo_embedding ON case_mo_assignment USING hnsw (embedding vector_cosine_ops);
COMMENT ON TABLE case_mo_assignment IS
  'Per-case MO embedding + cluster assignment (P15). embedding is an L2-normalised '
  'LSA vector; cosine distance (<=>) drives find_similar_cases.';
