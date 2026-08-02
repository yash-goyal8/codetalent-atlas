-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 05_extract_contributor_activity.sql — per-actor per-repository rollup
-- restricted to activity-passed (discovery_status = 'accepted') repositories,
-- feeding the spec 9.4 ContributorActivity table.
--
-- Semantics (documented; see docs/decisions.md):
--   * Human actors only (is_bot = FALSE); bots never become contributors. The
--     raw grids keep full bot detail for auditing.
--   * merged_pull_requests_authored is attributed to the MERGING actor: GH
--     Archive PullRequestEvent rows carry the closing actor, and the grid does
--     not retain the PR author login. Recorded as a source-field gap per spec
--     operating instruction 4; Milestone C+ can refine attribution.
--   * active_days sums per-month per-actor day counts, which is exact because
--     months are disjoint. active_months counts months with any qualifying
--     event.
--   * raw_contribution_points applies the config/scoring.yaml event weights
--     (releases and closed PRs contribute points via their weighted terms even
--     though 9.4 has no dedicated column for them — closed PRs carry weight 0
--     because the spec assigns no weight to unmerged closes).
--   * subdomains (spec 9.4) cannot be known before Milestone C classification;
--     the local Parquet export writes an empty list, documented there.
--   * Rows whose counted events are all zero (only uncounted actions, for
--     example PR 'reopened') are dropped.
--
-- Placeholders (see sql/00_profile_tables.sql for the full convention):
--   {grid_union}                                UNION ALL over month grids.
--   {project} / {dataset} / {repo_discovery_table}  validated identifiers.
--   {domain_id_literal}                         quoted domain id, e.g.
--                                               'cloud_devops'.
--   {weight_*}                                  event weights from
--                                               config/scoring.yaml.

-- statement: extract_contributor_activity
WITH events AS (
{grid_union}
),
accepted_repos AS (
  SELECT
    repo_name
  FROM
    `{project}.{dataset}.{repo_discovery_table}`
  WHERE
    discovery_status = 'accepted'
)
SELECT
  e.actor_login,
  e.repo_name,
  {domain_id_literal} AS domain_id,
  SUM(e.push_events) AS push_events,
  SUM(e.prs_opened) AS pull_requests_opened,
  SUM(e.prs_merged) AS merged_pull_requests_authored,
  SUM(e.reviews_submitted) AS reviews_submitted,
  SUM(e.issues_opened) AS issues_opened,
  SUM(e.issue_comments) AS issue_comments,
  SUM(e.active_days) AS active_days,
  COUNT(DISTINCT e.month) AS active_months,
  MIN(e.first_seen) AS first_seen,
  MAX(e.last_seen) AS last_seen,
  CAST(SUM(e.prs_merged) AS FLOAT64) * {weight_merged_pull_request}
    + CAST(SUM(e.reviews_submitted) AS FLOAT64) * {weight_pull_request_review}
    + CAST(SUM(e.prs_opened) AS FLOAT64) * {weight_pull_request_opened}
    + CAST(SUM(e.releases) AS FLOAT64) * {weight_release}
    + CAST(SUM(e.push_events) AS FLOAT64) * {weight_push_event}
    + CAST(SUM(e.issues_opened) AS FLOAT64) * {weight_issue_opened}
    + CAST(SUM(e.issue_comments) AS FLOAT64) * {weight_issue_comment}
    AS raw_contribution_points
FROM
  events AS e
INNER JOIN
  accepted_repos
USING (repo_name)
WHERE
  e.is_bot = FALSE
GROUP BY
  e.actor_login,
  e.repo_name
HAVING
  SUM(
    e.push_events + e.prs_opened + e.prs_closed + e.reviews_submitted
    + e.issues_opened + e.issue_comments + e.releases
  ) > 0
