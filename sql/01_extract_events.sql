-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 01_extract_events.sql — per-month (repo, actor) event grid materialization.
--
-- THE ONLY EXPENSIVE QUERY IN THE PIPELINE. One pass per pilot month over the
-- five required columns [type, repo.name, actor.login, created_at, payload] of
-- `githubarchive.month.{month}` (~58.5 GiB per month, measured 2026-08-01),
-- filtered to the six spec event types and grouped into a compact
-- (repo_name, actor_login) grid. Every downstream query (bot audit, repo
-- rollup, filters, contributor extraction, quality checks) reads only the
-- small grid tables this statement materializes — never GH Archive again.
--
-- Bots are FLAGGED (is_bot + the exact matching bot_pattern for auditability),
-- never dropped, so raw and human-filtered aggregates both stay derivable
-- (spec section 13).
--
-- active_day_mask is a per-month day-of-month bitmask (bit N-1 set when the
-- actor had a qualifying event on day N). BIT_OR across actors followed by
-- BIT_COUNT lets the repository rollup compute exact distinct active days
-- without carrying per-day rows.
--
-- Placeholders (see sql/00_profile_tables.sql for the full convention):
--   {month}            GH Archive month suffix, e.g. 202605 (validated YYYYMM).
--   {bot_pattern_case} CASE expression over actor_login rendered from
--                      config/bot_patterns.yaml; yields the first matching
--                      pattern label or NULL for humans.

-- statement: extract_events
WITH source_events AS (
  SELECT
    repo.name AS repo_name,
    actor.login AS actor_login,
    type,
    created_at,
    JSON_EXTRACT_SCALAR(payload, '$.action') AS action,
    JSON_EXTRACT_SCALAR(payload, '$.pull_request.merged') AS pr_merged,
    CAST(JSON_EXTRACT_SCALAR(payload, '$.distinct_size') AS INT64) AS push_distinct_size,
    CAST(JSON_EXTRACT_SCALAR(payload, '$.size') AS INT64) AS push_size
  FROM
    `githubarchive.month.{month}`
  WHERE
    type IN (
      'PushEvent',
      'PullRequestEvent',
      'PullRequestReviewEvent',
      'IssuesEvent',
      'IssueCommentEvent',
      'ReleaseEvent'
    )
),
grid AS (
  SELECT
    repo_name,
    actor_login,
    COUNTIF(type = 'PushEvent') AS push_events,
    -- Commits per push: payload $.distinct_size, falling back to $.size.
    SUM(IF(type = 'PushEvent', COALESCE(push_distinct_size, push_size, 0), 0))
      AS push_commit_count,
    COUNTIF(type = 'PullRequestEvent' AND action = 'opened') AS prs_opened,
    COUNTIF(type = 'PullRequestEvent' AND action = 'closed') AS prs_closed,
    COUNTIF(type = 'PullRequestEvent' AND action = 'closed' AND pr_merged = 'true')
      AS prs_merged,
    COUNTIF(type = 'PullRequestReviewEvent') AS reviews_submitted,
    COUNTIF(type = 'IssuesEvent' AND action = 'opened') AS issues_opened,
    COUNTIF(type = 'IssueCommentEvent') AS issue_comments,
    COUNTIF(type = 'ReleaseEvent') AS releases,
    COUNT(DISTINCT DATE(created_at)) AS active_days,
    BIT_OR(1 << (EXTRACT(DAY FROM created_at) - 1)) AS active_day_mask,
    MIN(DATE(created_at)) AS first_seen,
    MAX(DATE(created_at)) AS last_seen
  FROM
    source_events
  GROUP BY
    repo_name,
    actor_login
),
labeled AS (
  SELECT
    repo_name,
    actor_login,
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
    last_seen,
    {bot_pattern_case} AS bot_pattern
  FROM
    grid
)
SELECT
  repo_name,
  actor_login,
  {month} AS month,
  bot_pattern IS NOT NULL AS is_bot,
  bot_pattern,
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
FROM
  labeled
