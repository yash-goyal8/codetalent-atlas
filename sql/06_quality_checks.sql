-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 06_quality_checks.sql — data quality gates over the materialized discovery
-- tables (spec section 28 rows that apply to Phase 3). One row per check:
-- (check_name, failing_rows, status, requirement). Any 'fail' row stops the
-- pipeline before export. Results are fetched directly (no destination table)
-- so reruns always re-evaluate.
--
-- Placeholders (see sql/00_profile_tables.sql for the full convention):
--   {project} / {dataset} / {repo_discovery_table} / {contributor_table}
--       validated identifiers.
--   {grid_duplicate_total}
--       fragment summing duplicate (repo_name, actor_login) key counts across
--       every month grid table (built by sqlgen.grid_duplicate_total()).
--   {window_start} / {window_end}
--       pilot window dates (YYYY-MM-DD, validated).

-- statement: quality_checks
WITH repo AS (
  SELECT
    repo_name,
    unique_human_contributors,
    active_days,
    active_months,
    push_events,
    push_commit_count,
    pull_requests_opened,
    pull_requests_closed,
    merged_pull_requests,
    reviews_submitted,
    issues_opened,
    issue_comments,
    releases,
    weighted_activity_score,
    first_seen,
    last_seen,
    automation_event_share,
    single_actor_event_share,
    meaningful_events,
    discovery_status,
    exclusion_reason
  FROM
    `{project}.{dataset}.{repo_discovery_table}`
),
contributor AS (
  SELECT
    actor_login,
    repo_name,
    push_events,
    pull_requests_opened,
    merged_pull_requests_authored,
    reviews_submitted,
    issues_opened,
    issue_comments,
    active_days,
    active_months,
    first_seen,
    last_seen,
    raw_contribution_points
  FROM
    `{project}.{dataset}.{contributor_table}`
),
checks AS (
  SELECT
    'repo_date_bounds' AS check_name,
    (
      SELECT COUNT(*)
      FROM repo
      WHERE first_seen < DATE '{window_start}'
        OR last_seen > DATE '{window_end}'
        OR first_seen > last_seen
    ) AS failing_rows,
    'first_seen and last_seen within [{window_start}, {window_end}] and ordered'
      AS requirement
  UNION ALL
  SELECT
    'grid_duplicate_keys',
    {grid_duplicate_total},
    'each (repo_name, actor_login) pair unique within every month grid'
  UNION ALL
  SELECT
    'repo_duplicate_keys',
    (
      SELECT COUNT(*)
      FROM (
        SELECT repo_name
        FROM repo
        GROUP BY repo_name
        HAVING COUNT(*) > 1
      )
    ),
    'repo_name unique in the repository discovery table'
  UNION ALL
  SELECT
    'contributor_duplicate_keys',
    (
      SELECT COUNT(*)
      FROM (
        SELECT actor_login, repo_name
        FROM contributor
        GROUP BY actor_login, repo_name
        HAVING COUNT(*) > 1
      )
    ),
    'actor_login plus repo_name unique in the contributor activity table'
  UNION ALL
  SELECT
    'repo_non_negative_counts',
    (
      SELECT COUNT(*)
      FROM repo
      WHERE unique_human_contributors < 0
        OR active_days < 0
        OR active_months < 0
        OR push_events < 0
        OR push_commit_count < 0
        OR pull_requests_opened < 0
        OR pull_requests_closed < 0
        OR merged_pull_requests < 0
        OR reviews_submitted < 0
        OR issues_opened < 0
        OR issue_comments < 0
        OR releases < 0
        OR weighted_activity_score < 0
    ),
    'every repository counter and score non-negative'
  UNION ALL
  SELECT
    'contributor_non_negative_counts',
    (
      SELECT COUNT(*)
      FROM contributor
      WHERE push_events < 0
        OR pull_requests_opened < 0
        OR merged_pull_requests_authored < 0
        OR reviews_submitted < 0
        OR issues_opened < 0
        OR issue_comments < 0
        OR active_days < 0
        OR active_months < 0
        OR raw_contribution_points < 0
    ),
    'every contributor counter and score non-negative'
  UNION ALL
  SELECT
    'repo_share_bounds',
    (
      SELECT COUNT(*)
      FROM repo
      WHERE automation_event_share < 0
        OR automation_event_share > 1
        OR single_actor_event_share < 0
        OR single_actor_event_share > 1
    ),
    'automation and single-actor event shares within [0, 1]'
  UNION ALL
  SELECT
    'merged_within_closed',
    (
      SELECT COUNT(*)
      FROM repo
      WHERE merged_pull_requests > pull_requests_closed
    ),
    'merged pull requests never exceed closed pull requests'
  UNION ALL
  SELECT
    'meaningful_events_consistency',
    (
      SELECT COUNT(*)
      FROM repo
      WHERE meaningful_events != push_events + pull_requests_opened
        + pull_requests_closed + reviews_submitted + issues_opened
        + issue_comments + releases
    ),
    'meaningful_events equals the sum of counted human events'
  UNION ALL
  SELECT
    'status_reason_consistency',
    (
      SELECT COUNT(*)
      FROM repo
      WHERE (discovery_status = 'accepted' AND exclusion_reason IS NOT NULL)
        OR (discovery_status != 'accepted' AND exclusion_reason IS NULL)
    ),
    'accepted rows carry no exclusion_reason; all other rows carry one'
  UNION ALL
  SELECT
    'contributor_repo_membership',
    (
      SELECT COUNT(*)
      FROM contributor AS c
      LEFT JOIN repo AS r
        ON c.repo_name = r.repo_name AND r.discovery_status = 'accepted'
      WHERE r.repo_name IS NULL
    ),
    'every contributor row belongs to an accepted repository'
)
SELECT
  check_name,
  failing_rows,
  IF(failing_rows = 0, 'pass', 'fail') AS status,
  requirement
FROM
  checks
ORDER BY
  check_name
