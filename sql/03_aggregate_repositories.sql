-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 03_aggregate_repositories.sql — repository rollup across the month grids,
-- producing every spec 9.1 RepositoryActivitySummary field that GH Archive can
-- supply (discovery_status / exclusion_reason are assigned by
-- 04_apply_activity_filters.sql).
--
-- Field semantics (documented; see docs/decisions.md):
--   * All per-event-type counters, active_days, active_months, first_seen,
--     last_seen, meaningful_events, and weighted_activity_score are computed
--     over HUMAN (non-bot) events only. Bot activity is preserved separately in
--     automation_event_share = bot events / all events, and the raw grids keep
--     full bot detail (spec 13 auditability).
--   * single_actor_event_share = counted events of the most active human actor
--     divided by all counted human events (0 when there are none).
--   * unique_human_contributors counts human actors with at least one counted
--     event. Events of the six types whose action is not counted (for example
--     a PullRequestEvent with action='reopened') mark days as active but do not
--     appear in any counter.
--   * active_days is exact: per-month day bitmasks are BIT_OR-combined across
--     human actors, then BIT_COUNT-ed and summed over disjoint months.
--   * owner_login / repo_short_name derive from repo_name ("owner/name");
--     no extra source column is scanned.
--
-- Output bound (keeps the summary and the later REST fetch bounded; these are
-- bounding constants documented in codetalent.bigquery.dry_run, not config
-- thresholds): a repository enters the rollup when it has at least
-- {summary_min_human_contributors} unique human contributors OR it matches the
-- domain taxonomy name predicate with at least
-- {candidate_min_human_contributors} human contributor(s).
--
-- Placeholders (see sql/00_profile_tables.sql for the full convention):
--   {grid_union}                        UNION ALL over the month grid tables.
--   {taxonomy_predicate}                name-match predicate rendered from
--                                       config/cloud_devops_taxonomy.yaml
--                                       (positive_topics + positive_terms,
--                                       normalized; recall-limited by design —
--                                       Milestone C refines with topics and
--                                       descriptions).
--   {weight_*}                          event weights from config/scoring.yaml.
--   {summary_min_human_contributors}    summary bound (see above).
--   {candidate_min_human_contributors}  candidate floor bound (see above).

-- statement: aggregate_repositories
WITH events AS (
{grid_union}
),
per_actor AS (
  SELECT
    repo_name,
    actor_login,
    LOGICAL_OR(is_bot) AS is_bot,
    SUM(push_events) AS push_events,
    SUM(push_commit_count) AS push_commit_count,
    SUM(prs_opened) AS prs_opened,
    SUM(prs_closed) AS prs_closed,
    SUM(prs_merged) AS prs_merged,
    SUM(reviews_submitted) AS reviews_submitted,
    SUM(issues_opened) AS issues_opened,
    SUM(issue_comments) AS issue_comments,
    SUM(releases) AS releases,
    SUM(
      push_events + prs_opened + prs_closed + reviews_submitted
      + issues_opened + issue_comments + releases
    ) AS counted_events,
    MIN(first_seen) AS first_seen,
    MAX(last_seen) AS last_seen
  FROM
    events
  GROUP BY
    repo_name,
    actor_login
),
human_month_days AS (
  SELECT
    repo_name,
    month,
    BIT_OR(active_day_mask) AS day_mask
  FROM
    events
  WHERE
    is_bot = FALSE
  GROUP BY
    repo_name,
    month
),
repo_days AS (
  SELECT
    repo_name,
    SUM(BIT_COUNT(day_mask)) AS active_days,
    COUNT(*) AS active_months
  FROM
    human_month_days
  GROUP BY
    repo_name
),
per_repo AS (
  SELECT
    repo_name,
    COUNT(DISTINCT IF(NOT is_bot AND counted_events > 0, actor_login, NULL))
      AS unique_human_contributors,
    SUM(IF(NOT is_bot, push_events, 0)) AS push_events,
    SUM(IF(NOT is_bot, push_commit_count, 0)) AS push_commit_count,
    SUM(IF(NOT is_bot, prs_opened, 0)) AS prs_opened,
    SUM(IF(NOT is_bot, prs_closed, 0)) AS prs_closed,
    SUM(IF(NOT is_bot, prs_merged, 0)) AS prs_merged,
    SUM(IF(NOT is_bot, reviews_submitted, 0)) AS reviews_submitted,
    SUM(IF(NOT is_bot, issues_opened, 0)) AS issues_opened,
    SUM(IF(NOT is_bot, issue_comments, 0)) AS issue_comments,
    SUM(IF(NOT is_bot, releases, 0)) AS releases,
    SUM(IF(NOT is_bot, counted_events, 0)) AS human_counted_events,
    SUM(IF(is_bot, counted_events, 0)) AS bot_counted_events,
    MAX(IF(NOT is_bot, counted_events, NULL)) AS top_human_actor_events,
    MIN(IF(NOT is_bot, first_seen, NULL)) AS first_seen,
    MAX(IF(NOT is_bot, last_seen, NULL)) AS last_seen
  FROM
    per_actor
  GROUP BY
    repo_name
)
SELECT
  r.repo_name,
  IFNULL(SPLIT(r.repo_name, '/')[SAFE_OFFSET(0)], '') AS owner_login,
  IFNULL(SPLIT(r.repo_name, '/')[SAFE_OFFSET(1)], '') AS repo_short_name,
  r.unique_human_contributors,
  IFNULL(d.active_days, 0) AS active_days,
  IFNULL(d.active_months, 0) AS active_months,
  r.push_events,
  r.push_commit_count,
  r.prs_opened AS pull_requests_opened,
  r.prs_closed AS pull_requests_closed,
  r.prs_merged AS merged_pull_requests,
  r.reviews_submitted,
  r.issues_opened,
  r.issue_comments,
  r.releases,
  CAST(r.prs_merged AS FLOAT64) * {weight_merged_pull_request}
    + CAST(r.reviews_submitted AS FLOAT64) * {weight_pull_request_review}
    + CAST(r.prs_opened AS FLOAT64) * {weight_pull_request_opened}
    + CAST(r.releases AS FLOAT64) * {weight_release}
    + CAST(r.push_events AS FLOAT64) * {weight_push_event}
    + CAST(r.issues_opened AS FLOAT64) * {weight_issue_opened}
    + CAST(r.issue_comments AS FLOAT64) * {weight_issue_comment}
    AS weighted_activity_score,
  r.first_seen,
  r.last_seen,
  IFNULL(
    SAFE_DIVIDE(r.bot_counted_events, r.bot_counted_events + r.human_counted_events),
    0
  ) AS automation_event_share,
  IFNULL(SAFE_DIVIDE(r.top_human_actor_events, r.human_counted_events), 0)
    AS single_actor_event_share,
  r.human_counted_events AS meaningful_events,
  {taxonomy_predicate} AS is_taxonomy_candidate
FROM
  per_repo AS r
LEFT JOIN
  repo_days AS d
USING (repo_name)
WHERE
  r.unique_human_contributors >= {summary_min_human_contributors}
  OR (
    {taxonomy_predicate}
    AND r.unique_human_contributors >= {candidate_min_human_contributors}
  )
