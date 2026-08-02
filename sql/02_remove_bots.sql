-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 02_remove_bots.sql — bot exclusion audit plus the human-only grid view.
--
-- Nothing is deleted anywhere: the month grids keep every actor with is_bot and
-- the matching bot_pattern. This file (a) materializes an audit table counting
-- excluded actors and events by pattern (spec section 13: record excluded
-- counts by pattern) and (b) creates a human-only VIEW over the grids so
-- human-filtered aggregates are directly queryable next to the raw grids.
-- Downstream statements (03/05) additionally embed `is_bot = FALSE` predicates
-- so both raw and human-filtered aggregates stay derivable from the same grids.
--
-- Placeholders (see sql/00_profile_tables.sql for the full convention):
--   {grid_union}  UNION ALL over the per-month grid tables selecting the full
--                 explicit grid column list (built by sqlgen.grid_union()).
--   {project} / {dataset} / {human_view}  validated identifiers.

-- statement: bot_exclusion_audit
WITH events AS (
{grid_union}
)
SELECT
  IF(is_bot, 'bot', 'human') AS actor_class,
  bot_pattern,
  COUNT(DISTINCT actor_login) AS distinct_actors,
  COUNT(DISTINCT repo_name) AS distinct_repos,
  COUNT(*) AS grid_rows,
  SUM(
    push_events + prs_opened + prs_closed + reviews_submitted
    + issues_opened + issue_comments + releases
  ) AS total_counted_events
FROM
  events
GROUP BY
  actor_class,
  bot_pattern
ORDER BY
  actor_class,
  total_counted_events DESC

-- statement: human_grid_view
CREATE OR REPLACE VIEW `{project}.{dataset}.{human_view}` AS
SELECT
  repo_name,
  actor_login,
  month,
  push_events,
  push_commit_count,
  prs_opened,
  prs_closed,
  prs_merged,
  reviews_submitted,
  issues_opened,
  issue_comments,
  releases,
  active_days,
  active_day_mask,
  first_seen,
  last_seen
FROM (
{grid_union}
)
WHERE
  is_bot = FALSE
