-- =============================================================================
-- KSP FIR SYSTEM — source schema
-- Transcribed from "Police_FIR_ER_Diagram", Karnataka Police Department.
--
-- CONVENTIONS
--   * snake_case throughout; the original PascalCase name is recorded in a
--     COMMENT on every table and on any column whose name was changed.
--     Rationale: unquoted identifiers in Postgres fold to lowercase, so
--     "CaseMaster" would become casemaster anyway. snake_case + comments keeps
--     it clean and keeps the mapping back to the source explicit.
--   * Every deviation from the supplied diagram is marked  -- [FIX]  or
--     -- [INFERRED]  and explained. Nothing is changed silently.
--
-- DEVIATIONS FROM THE SUPPLIED DIAGRAM (see PLAN.md §11)
--   [FIX-1] ActSectionAssociation.ActID and .SectionID are typed INT but point
--           at Act.ActCode / Section.SectionCode which are VARCHAR.
--           CrimeHeadActSection.ActCode is correctly VARCHAR. Standardised on
--           VARCHAR. Confirm with organisers.
--   [FIX-2] Section has no declared primary key. Added composite (act_code,
--           section_code).
--   [FIX-3] ArrestSurrender carries BOTH a direct AccusedMasterID FK and an
--           inv_arrestsurrenderaccused junction. Junction treated as
--           authoritative; the direct FK is retained but nullable and marked
--           deprecated. Confirm with organisers.
--   [INFERRED-1] inv_arrestsurrenderaccused is referenced in the relationship
--           matrix but never defined. Columns inferred.
--   [INFERRED-2] Inv_OccuranceTime is referenced (1:1 with CaseMaster) but
--           never defined. Columns inferred.
--   [INFERRED-3] GenderID is described as "lookup value" (M/F/T) across four
--           tables but no gender table is defined. Added gender_master.
-- =============================================================================

SET search_path TO ksp, public;

-- -----------------------------------------------------------------------------
-- Geography and organisational hierarchy
-- -----------------------------------------------------------------------------

CREATE TABLE state (
    state_id       INTEGER PRIMARY KEY,
    state_name     VARCHAR(120) NOT NULL,
    nationality_id INTEGER,
    active         BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE state IS 'Source: State';

CREATE TABLE district (
    district_id   INTEGER PRIMARY KEY,
    district_name VARCHAR(120) NOT NULL,
    state_id      INTEGER REFERENCES state(state_id),
    active        BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE district IS 'Source: District';
CREATE INDEX idx_district_state ON district(state_id);

CREATE TABLE unit_type (
    unit_type_id   INTEGER PRIMARY KEY,
    unit_type_name VARCHAR(120) NOT NULL,
    city_dist_state VARCHAR(20),
    hierarchy      INTEGER,
    active         BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE unit_type IS 'Source: UnitType';
COMMENT ON COLUMN unit_type.city_dist_state IS 'Source: CityDistState — operational level City/District/State';
COMMENT ON COLUMN unit_type.hierarchy IS 'Lower number = higher authority';

CREATE TABLE unit (
    unit_id        INTEGER PRIMARY KEY,
    unit_name      VARCHAR(200) NOT NULL,
    type_id        INTEGER REFERENCES unit_type(unit_type_id),
    parent_unit    INTEGER REFERENCES unit(unit_id),  -- self-reference: drives RBAC scoping
    nationality_id INTEGER,
    state_id       INTEGER REFERENCES state(state_id),
    district_id    INTEGER REFERENCES district(district_id),
    active         BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE unit IS 'Source: Unit — police stations and higher formations';
COMMENT ON COLUMN unit.parent_unit IS
  'Self-referencing hierarchy. Used with rank.hierarchy for RBAC scope resolution (P9).';
CREATE INDEX idx_unit_parent ON unit(parent_unit);
CREATE INDEX idx_unit_district ON unit(district_id);

CREATE TABLE rank (
    rank_id   INTEGER PRIMARY KEY,
    rank_name VARCHAR(120) NOT NULL,
    hierarchy INTEGER,
    active    BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE rank IS 'Source: Rank';
COMMENT ON COLUMN rank.hierarchy IS 'Lower number = higher rank';

CREATE TABLE designation (
    designation_id   INTEGER PRIMARY KEY,
    designation_name VARCHAR(120) NOT NULL,
    sort_order       INTEGER,
    active           BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE designation IS 'Source: Designation';

-- [INFERRED-3] Not in the supplied diagram; GenderID is referenced as a
-- "lookup value" by accused, victim, complainant_details and employee.
CREATE TABLE gender_master (
    gender_id   INTEGER PRIMARY KEY,
    gender_code CHAR(1) NOT NULL UNIQUE,
    gender_name VARCHAR(40) NOT NULL
);
COMMENT ON TABLE gender_master IS
  '[INFERRED-3] Not defined in the supplied diagram. The diagram describes '
  'GenderID as a lookup with values M/F/T (transgender explicitly included).';
INSERT INTO gender_master (gender_id, gender_code, gender_name) VALUES
    (1, 'M', 'Male'), (2, 'F', 'Female'), (3, 'T', 'Transgender');

CREATE TABLE employee (
    employee_id           INTEGER PRIMARY KEY,
    district_id           INTEGER REFERENCES district(district_id),
    unit_id               INTEGER REFERENCES unit(unit_id),
    rank_id               INTEGER REFERENCES rank(rank_id),
    designation_id        INTEGER REFERENCES designation(designation_id),
    kgid                  VARCHAR(40),
    first_name            VARCHAR(160),
    employee_dob          DATE,
    gender_id             INTEGER REFERENCES gender_master(gender_id),
    blood_group_id        INTEGER,
    physically_challenged BOOLEAN DEFAULT FALSE,
    appointment_date      DATE
);
COMMENT ON TABLE employee IS 'Source: Employee — police personnel';
COMMENT ON COLUMN employee.kgid IS 'Karnataka Government ID';
CREATE INDEX idx_employee_unit ON employee(unit_id);
CREATE INDEX idx_employee_district ON employee(district_id);

CREATE TABLE court (
    court_id    INTEGER PRIMARY KEY,
    court_name  VARCHAR(240) NOT NULL,
    district_id INTEGER REFERENCES district(district_id),
    state_id    INTEGER REFERENCES state(state_id),
    active      BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE court IS 'Source: Court';

-- -----------------------------------------------------------------------------
-- Legal framework
-- -----------------------------------------------------------------------------

CREATE TABLE act (
    act_code        VARCHAR(40) PRIMARY KEY,
    act_description VARCHAR(500),
    short_name      VARCHAR(120),
    active          BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE act IS 'Source: Act — e.g. IPC, BNS, NDPS';

CREATE TABLE section (
    act_code            VARCHAR(40) NOT NULL REFERENCES act(act_code),
    section_code        VARCHAR(40) NOT NULL,
    section_description VARCHAR(1000),
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT pk_section PRIMARY KEY (act_code, section_code)  -- [FIX-2]
);
COMMENT ON TABLE section IS 'Source: Section';
COMMENT ON CONSTRAINT pk_section ON section IS
  '[FIX-2] The supplied diagram declares no primary key on Section.';

CREATE TABLE crime_head (
    crime_head_id    INTEGER PRIMARY KEY,
    crime_group_name VARCHAR(240) NOT NULL,
    active           BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE crime_head IS 'Source: CrimeHead — major head, e.g. Crimes Against Body';

CREATE TABLE crime_sub_head (
    crime_sub_head_id INTEGER PRIMARY KEY,
    crime_head_id     INTEGER REFERENCES crime_head(crime_head_id),
    crime_head_name   VARCHAR(240) NOT NULL,
    seq_id            INTEGER
);
COMMENT ON TABLE crime_sub_head IS 'Source: CrimeSubHead — e.g. Murder, Robbery';
CREATE INDEX idx_crime_sub_head_parent ON crime_sub_head(crime_head_id);

CREATE TABLE crime_head_act_section (
    crime_head_id INTEGER NOT NULL REFERENCES crime_head(crime_head_id),
    act_code      VARCHAR(40) NOT NULL,
    section_code  VARCHAR(40) NOT NULL,
    CONSTRAINT pk_crime_head_act_section PRIMARY KEY (crime_head_id, act_code, section_code),
    CONSTRAINT fk_chas_section FOREIGN KEY (act_code, section_code)
        REFERENCES section(act_code, section_code)
);
COMMENT ON TABLE crime_head_act_section IS 'Source: CrimeHeadActSection';

-- -----------------------------------------------------------------------------
-- Case lookups
-- -----------------------------------------------------------------------------

CREATE TABLE case_category (
    case_category_id INTEGER PRIMARY KEY,
    lookup_value     VARCHAR(80) NOT NULL
);
COMMENT ON TABLE case_category IS 'Source: CaseCategory — FIR, UDR, PAR, Zero FIR';
INSERT INTO case_category (case_category_id, lookup_value) VALUES
    (1, 'FIR'), (3, 'UDR'), (4, 'PAR'), (8, 'Zero FIR');
COMMENT ON COLUMN case_category.case_category_id IS
  'Matches the leading digit of crime_no. Seeded from the examples in the ER diagram; '
  'confirm the full list with organisers.';

CREATE TABLE gravity_offence (
    gravity_offence_id INTEGER PRIMARY KEY,
    lookup_value       VARCHAR(80) NOT NULL
);
COMMENT ON TABLE gravity_offence IS 'Source: GravityOffence — Heinous / Non-Heinous';

CREATE TABLE case_status_master (
    case_status_id   INTEGER PRIMARY KEY,
    case_status_name VARCHAR(120) NOT NULL
);
COMMENT ON TABLE case_status_master IS 'Source: CaseStatusMaster';

CREATE TABLE caste_master (
    caste_master_id   INTEGER PRIMARY KEY,
    caste_master_name VARCHAR(160) NOT NULL
);
COMMENT ON TABLE caste_master IS 'Source: CasteMaster — referenced ONLY by complainant_details';

CREATE TABLE religion_master (
    religion_id   INTEGER PRIMARY KEY,
    religion_name VARCHAR(120) NOT NULL
);
COMMENT ON TABLE religion_master IS 'Source: ReligionMaster — referenced ONLY by complainant_details';

CREATE TABLE occupation_master (
    occupation_id   INTEGER PRIMARY KEY,
    occupation_name VARCHAR(160) NOT NULL
);
COMMENT ON TABLE occupation_master IS 'Source: OccupationMaster — referenced ONLY by complainant_details';

-- -----------------------------------------------------------------------------
-- Case core
-- -----------------------------------------------------------------------------

CREATE TABLE case_master (
    case_master_id        INTEGER PRIMARY KEY,
    crime_no              VARCHAR(40),
    case_no               VARCHAR(40),
    crime_registered_date DATE,
    police_person_id      INTEGER REFERENCES employee(employee_id),
    police_station_id     INTEGER REFERENCES unit(unit_id),
    case_category_id      INTEGER REFERENCES case_category(case_category_id),
    gravity_offence_id    INTEGER REFERENCES gravity_offence(gravity_offence_id),
    crime_major_head_id   INTEGER REFERENCES crime_head(crime_head_id),
    crime_minor_head_id   INTEGER REFERENCES crime_sub_head(crime_sub_head_id),
    case_status_id        INTEGER REFERENCES case_status_master(case_status_id),
    court_id              INTEGER REFERENCES court(court_id),
    incident_from_date    TIMESTAMP,
    incident_to_date      TIMESTAMP,
    info_received_ps_date TIMESTAMP,
    latitude              NUMERIC(10, 7),
    longitude             NUMERIC(10, 7),
    brief_facts           TEXT
);
COMMENT ON TABLE case_master IS 'Source: CaseMaster — one row per FIR/UDR/PAR/Zero FIR';
COMMENT ON COLUMN case_master.crime_no IS
  'Format: 1 digit case category + 4 digit district + 4 digit police station + '
  '4 digit year + 5 digit serial. e.g. FIR 104430006202600001. Parsed by ingest/loader.py (P3).';
COMMENT ON COLUMN case_master.case_no IS 'Last 9 digits of crime_no: YYYY + 5-digit serial';
COMMENT ON COLUMN case_master.brief_facts IS
  'Source: BriefFacts NVARCHAR(MAX). The only unstructured field in the schema and the '
  'sole basis for MO derivation (P15). Expect mixed Kannada/English/transliterated text. '
  'NEVER modify — the translation lands in derived.case_translation.';
COMMENT ON COLUMN case_master.latitude IS
  'Expect a high null rate. Fall back to district centroid and mark the point as inferred (P13).';

CREATE INDEX idx_case_master_crime_no ON case_master(crime_no);
CREATE INDEX idx_case_master_station ON case_master(police_station_id);
CREATE INDEX idx_case_master_registered ON case_master(crime_registered_date);
CREATE INDEX idx_case_master_major_head ON case_master(crime_major_head_id);
CREATE INDEX idx_case_master_status ON case_master(case_status_id);
CREATE INDEX idx_case_master_category ON case_master(case_category_id);
-- Spatial index for hotspot scans (P13). Partial: skips the null-coordinate rows.
CREATE INDEX idx_case_master_geom ON case_master
    USING GIST (ST_SetSRID(ST_MakePoint(longitude::float8, latitude::float8), 4326))
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- [INFERRED-2] Referenced in the relationship matrix as 1:1 with CaseMaster
-- ("One FIR has one occurrence time/location record") but never defined.
-- Note the overlap with case_master.latitude/longitude — ask organisers which
-- is authoritative before relying on either.
CREATE TABLE inv_occurance_time (
    case_master_id     INTEGER PRIMARY KEY REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    occurrence_from    TIMESTAMP,
    occurrence_to      TIMESTAMP,
    place_of_offence   VARCHAR(500),
    latitude           NUMERIC(10, 7),
    longitude          NUMERIC(10, 7),
    beat_id            INTEGER,
    distance_from_ps   NUMERIC(8, 2)
);
COMMENT ON TABLE inv_occurance_time IS
  '[INFERRED-2] Referenced in the relationship matrix (1:1 with CaseMaster) but never '
  'defined in the supplied diagram. ALL COLUMNS ARE ASSUMPTIONS. Duplicates '
  'case_master.latitude/longitude — authority unresolved. See PLAN.md §11 items 2 and 4.';

-- -----------------------------------------------------------------------------
-- Parties
-- -----------------------------------------------------------------------------

CREATE TABLE complainant_details (
    complainant_id   INTEGER PRIMARY KEY,
    case_master_id   INTEGER REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    complainant_name VARCHAR(300),
    age_year         INTEGER,
    occupation_id    INTEGER REFERENCES occupation_master(occupation_id),
    religion_id      INTEGER REFERENCES religion_master(religion_id),
    caste_id         INTEGER REFERENCES caste_master(caste_master_id),
    gender_id        INTEGER REFERENCES gender_master(gender_id)
);
COMMENT ON TABLE complainant_details IS
  'Source: ComplainantDetails. NOTE: this is the ONLY table carrying caste, religion and '
  'occupation. Offender demographic profiling is therefore impossible by construction — '
  'see PLAN.md §5. Sociological analysis is victimisation-side only.';
CREATE INDEX idx_complainant_case ON complainant_details(case_master_id);

CREATE TABLE victim (
    victim_master_id INTEGER PRIMARY KEY,
    case_master_id   INTEGER REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    victim_name      VARCHAR(300),
    age_year         INTEGER,
    gender_id        INTEGER REFERENCES gender_master(gender_id),
    victim_police    BOOLEAN
);
COMMENT ON TABLE victim IS 'Source: Victim';
COMMENT ON COLUMN victim.victim_police IS 'Source: VictimPolice — 1 if the victim is a police officer';
CREATE INDEX idx_victim_case ON victim(case_master_id);

CREATE TABLE accused (
    accused_master_id INTEGER PRIMARY KEY,
    case_master_id    INTEGER REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    accused_name      VARCHAR(300),
    age_year          INTEGER,
    gender_id         INTEGER REFERENCES gender_master(gender_id),
    person_id         VARCHAR(20)
);
COMMENT ON TABLE accused IS
  'Source: Accused. CRITICAL: accused_master_id is a ROW ID SCOPED TO ONE FIR, not a '
  'person identifier. There is no person entity in this schema. Never join on it to find '
  '"the same person" — use derived.person_cluster_member instead. See CLAUDE.md.';
COMMENT ON COLUMN accused.person_id IS
  'Source: PersonID — ordering label within the FIR (A1, A2, A3). NOT a person identifier.';
COMMENT ON COLUMN accused.accused_name IS
  'Free text. Carries embedded structure: patronymic (S/o, D/o, W/o, C/o) and aliases '
  '("Ramesh @ Rami"). Parsed by er/names.py (P5).';
CREATE INDEX idx_accused_case ON accused(case_master_id);
CREATE INDEX idx_accused_name_trgm ON accused USING GIN (accused_name gin_trgm_ops);

CREATE TABLE act_section_association (
    case_master_id   INTEGER NOT NULL REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    act_code         VARCHAR(40) NOT NULL,   -- [FIX-1] was ActID INT
    section_code     VARCHAR(40) NOT NULL,   -- [FIX-1] was SectionID INT
    act_order_id     INTEGER,
    section_order_id INTEGER,
    CONSTRAINT pk_act_section_association PRIMARY KEY (case_master_id, act_code, section_code),
    CONSTRAINT fk_asa_section FOREIGN KEY (act_code, section_code)
        REFERENCES section(act_code, section_code)
);
COMMENT ON TABLE act_section_association IS 'Source: ActSectionAssociation';
COMMENT ON COLUMN act_section_association.act_code IS
  '[FIX-1] Diagram types this as ActID INT while Act.ActCode is VARCHAR. '
  'Standardised on VARCHAR to match CrimeHeadActSection. Confirm with organisers.';

-- -----------------------------------------------------------------------------
-- Arrest and prosecution
-- -----------------------------------------------------------------------------

CREATE TABLE arrest_surrender (
    arrest_surrender_id         INTEGER PRIMARY KEY,
    case_master_id              INTEGER REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    arrest_surrender_type_id    INTEGER,
    arrest_surrender_date       DATE,
    arrest_surrender_state_id   INTEGER REFERENCES state(state_id),
    arrest_surrender_district_id INTEGER REFERENCES district(district_id),
    police_station_id           INTEGER REFERENCES unit(unit_id),
    io_id                       INTEGER REFERENCES employee(employee_id),
    court_id                    INTEGER REFERENCES court(court_id),
    accused_master_id           INTEGER REFERENCES accused(accused_master_id),  -- [FIX-3] deprecated
    is_accused                  BOOLEAN,
    is_complainant_accused      BOOLEAN
);
COMMENT ON TABLE arrest_surrender IS 'Source: ArrestSurrender';
COMMENT ON COLUMN arrest_surrender.accused_master_id IS
  '[FIX-3] DEPRECATED. The diagram carries both this direct FK and the '
  'inv_arrest_surrender_accused junction. The junction is treated as authoritative '
  'because one arrest event can cover multiple accused. Confirm with organisers.';
COMMENT ON COLUMN arrest_surrender.arrest_surrender_date IS
  'Drives the chargesheet deadline watch (P11) together with chargesheet_details.cs_date.';
CREATE INDEX idx_arrest_case ON arrest_surrender(case_master_id);
CREATE INDEX idx_arrest_date ON arrest_surrender(arrest_surrender_date);
CREATE INDEX idx_arrest_io ON arrest_surrender(io_id);

-- [INFERRED-1] Referenced in the relationship matrix but never defined.
-- This is the co-offending signal that collective entity resolution depends on (P7).
CREATE TABLE inv_arrest_surrender_accused (
    arrest_surrender_id INTEGER NOT NULL REFERENCES arrest_surrender(arrest_surrender_id) ON DELETE CASCADE,
    accused_master_id   INTEGER NOT NULL REFERENCES accused(accused_master_id) ON DELETE CASCADE,
    CONSTRAINT pk_inv_arrest_surrender_accused PRIMARY KEY (arrest_surrender_id, accused_master_id)
);
COMMENT ON TABLE inv_arrest_surrender_accused IS
  '[INFERRED-1] Referenced in the relationship matrix but never defined in the supplied '
  'diagram. COLUMNS ARE ASSUMPTIONS. This junction is the co-arrest signal that drives '
  'collective entity resolution (P7) — if the real structure differs, P7 needs revisiting. '
  'HIGH PRIORITY question for organisers. See PLAN.md §11 items 2 and 3.';
CREATE INDEX idx_iasa_accused ON inv_arrest_surrender_accused(accused_master_id);

CREATE TABLE chargesheet_details (
    cs_id            INTEGER PRIMARY KEY,
    case_master_id   INTEGER REFERENCES case_master(case_master_id) ON DELETE CASCADE,
    cs_date          TIMESTAMP,
    cs_type          CHAR(1),
    police_person_id INTEGER REFERENCES employee(employee_id),
    CONSTRAINT ck_cs_type CHECK (cs_type IS NULL OR cs_type IN ('A', 'B', 'C'))
);
COMMENT ON TABLE chargesheet_details IS 'Source: ChargesheetDetails';
COMMENT ON COLUMN chargesheet_details.cs_type IS
  'A = Chargesheet, B = False Case, C = Undetected. The only supervised outcome label in '
  'the entire schema — drives the undetected-case risk model (P16) and false-case-rate '
  'analytics. Treat as precious.';
CREATE INDEX idx_chargesheet_case ON chargesheet_details(case_master_id);
CREATE INDEX idx_chargesheet_type ON chargesheet_details(cs_type);
