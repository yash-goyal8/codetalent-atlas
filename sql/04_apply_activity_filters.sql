-- CodeTalent Atlas — Phase 3 discovery (Milestone B).
-- 04_apply_activity_filters.sql — discovery funnel statuses on the repository
-- rollup (spec 3.3 / 11 / 13).
--
-- Funnel definitions:
--   * discovered candidate  = taxonomy name match AND the minimal candidacy
--     floor (>= {candidate_min_human_contributors} human contributor(s) and
--     >= {candidate_min_meaningful_events} counted human event(s)); statuses
--     'accepted' or 'excluded'. Pilot target: 10,000+.
--   * activity-passed       = candidate meeting every config/repo_filters.yaml
--     minimum; status 'accepted'. Pilot target: 5,000+.
--   * pull_requests_or_reviews = pull_requests_opened + reviews_submitted
--     (documented definition; closed-only PR lifecycles are not counted).
--
-- discovery_status values (all rows of the bounded rollup get one):
--   'accepted'       candidate passing every repo_filters minimum
--                    (exclusion_reason NULL).
--   'excluded'       candidate failing at least one minimum; exclusion_reason
--                    lists every failed minimum, ';'-separated.
--   'below_floor'    taxonomy name match but below the candidacy floor.
--   'not_candidate'  in the rollup only via the human-contributor bound; no
--                    taxonomy name match.
--
-- Placeholders (see sql/00_profile_tables.sql for the full convention):
--   {project} / {dataset} / {repo_activity_table}  validated identifiers.
--   {min_unique_human_contributors} {min_meaningful_events}
--   {min_pull_requests_or_reviews} {min_active_months}
--       minimums rendered from config/repo_filters.yaml.
--   {candidate_min_human_contributors} {candidate_min_meaningful_events}
--       candidacy floor bounds documented in codetalent.bigquery.dry_run.

-- statement: apply_activity_filters
WITH repo AS (
  SELECT
    repo_name,
    owner_login,
    repo_short_name,
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
    is_taxonomy_candidate,
    pull_requests_opened + reviews_submitted AS pull_requests_or_reviews
  FROM
    `{project}.{dataset}.{repo_activity_table}`
),
evaluated AS (
  SELECT
    repo_name,
    owner_login,
    repo_short_name,
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
    is_taxonomy_candidate,
    pull_requests_or_reviews,
    (
      is_taxonomy_candidate
      AND unique_human_contributors >= {candidate_min_human_contributors}
      AND meaningful_events >= {candidate_min_meaningful_events}
    ) AS is_candidate,
    NULLIF(
      ARRAY_TO_STRING(
        [
          IF(
            unique_human_contributors < {min_unique_human_contributors},
            'unique_human_contributors<{min_unique_human_contributors}',
            NULL
          ),
          IF(
            meaningful_events < {min_meaningful_events},
            'meaningful_events<{min_meaningful_events}',
            NULL
          ),
          IF(
            pull_requests_or_reviews < {min_pull_requests_or_reviews},
            'pull_requests_or_reviews<{min_pull_requests_or_reviews}',
            NULL
          ),
          IF(
            active_months < {min_active_months},
            'active_months<{min_active_months}',
            NULL
          )
        ],
        ';'
      ),
      ''
    ) AS failed_minimums
  FROM
    repo
)
SELECT
  repo_name,
  owner_login,
  repo_short_name,
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
  is_taxonomy_candidate,
  pull_requests_or_reviews,
  -- Activity minimums are domain-agnostic (config/repo_filters.yaml carries no
  -- relevance condition): any repository passing them is 'accepted'. Domain
  -- relevance is Phase 2 classification over enriched metadata (Milestone C);
  -- the taxonomy name match stays available as the is_taxonomy_candidate
  -- signal. 'excluded'/'below_floor' apply to name-matched discovery
  -- candidates that fail the minimums or the candidate floor.
  CASE
    WHEN failed_minimums IS NULL THEN 'accepted'
    WHEN NOT is_taxonomy_candidate THEN 'not_candidate'
    WHEN NOT is_candidate THEN 'below_floor'
    ELSE 'excluded'
  END AS discovery_status,
  CASE
    WHEN failed_minimums IS NULL THEN NULL
    WHEN NOT is_taxonomy_candidate THEN 'no_taxonomy_name_match'
    WHEN NOT is_candidate THEN 'below_candidate_activity_floor'
    ELSE failed_minimums
  END AS exclusion_reason
FROM
  evaluated
