-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 00_profile_tables.sql — DRY-RUN ONLY column-group cost profiling.
--
-- NEVER EXECUTE THESE STATEMENTS. They exist so the dry-run planner can price
-- how many bytes each column group of a GH Archive month table would scan
-- (BigQuery charges by columns referenced, so the estimate equals the full
-- column scan regardless of any WHERE clause). Reference measurements from
-- 2026-08-01: month.202605 key columns ~6.54 GiB, payload ~51.97 GiB.
--
-- Placeholder convention (shared by every template in sql/):
--   * Named placeholders of the form {snake_case} are rendered by
--     codetalent.bigquery.sqlgen.render_statement() before any dry run or
--     execution. Rendering is strict: a missing or unused parameter is an error,
--     and no placeholder may remain unrendered.
--   * {project} / {dataset} / table-name placeholders are validated identifiers.
--   * {month} is a GH Archive month-table suffix (YYYYMM), validated.
--   * SQL fragments (for example {bot_pattern_case} or {grid_union}) are built
--     exclusively by audited helpers in sqlgen.py; every string literal passes
--     through sql_string_literal()/sql_raw_regex_literal() escaping.
--   * Numeric placeholders ({weight_*}, {min_*}) are rendered from
--     config/scoring.yaml and config/repo_filters.yaml at render time. No
--     scoring weight or threshold number is hardcoded in SQL.
--   * Statements are delimited by lines of the form "-- statement: <name>".
--
-- No SELECT * anywhere: columns are always listed explicitly (spec section 13).

-- statement: profile_key_columns
SELECT
  type,
  repo.name AS repo_name,
  actor.login AS actor_login,
  created_at
FROM
  `githubarchive.month.{month}`

-- statement: profile_payload_column
SELECT
  payload
FROM
  `githubarchive.month.{month}`

-- statement: profile_discovery_columns
SELECT
  type,
  repo.name AS repo_name,
  actor.login AS actor_login,
  created_at,
  payload
FROM
  `githubarchive.month.{month}`
