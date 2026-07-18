-- Extensions and schemas.
-- Runs first (docker-entrypoint-initdb.d executes *.sql in filename order).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy name matching (er/)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch; -- metaphone/levenshtein baseline (er/)

-- ksp     = the Karnataka State Police schema, as supplied in the ER diagram.
--           Treat as read-only source of truth. Do not add our columns here.
-- derived = everything we compute. person_cluster, MO clusters, risk scores, alerts.
CREATE SCHEMA IF NOT EXISTS ksp;
CREATE SCHEMA IF NOT EXISTS derived;

COMMENT ON SCHEMA ksp IS
  'Karnataka State Police source schema, transcribed from the supplied ER diagram. '
  'Read-only. Never add derived columns here — use the derived schema.';
COMMENT ON SCHEMA derived IS
  'Everything this project computes. Safe to drop and rebuild from ksp.';
