#!/usr/bin/env bash
# BigQuery Sandbox setup for GH Archive discovery (spec Phase 1, Milestone B).
# This script will walk through the zero-cost sandbox setup once Milestone B lands.
set -euo pipefail

cat <<'EOF'
CodeTalent Atlas — BigQuery Sandbox setup (Milestone B)

Planned steps:
  1. Create a Google Cloud project in BigQuery Sandbox mode (no billing attached).
  2. Confirm access to the public `githubarchive` monthly tables.
  3. Set GOOGLE_CLOUD_PROJECT in your local .env (never commit it).
  4. Verify the dry-run guard: `codetalent bq dry-run --start 2026-05-01 --end 2026-07-31`.
  5. Keep pilot usage within the 250 GiB budget (BIGQUERY_MAX_BYTES_PHASE3).
EOF

echo "not yet implemented — Milestone B" >&2
exit 1
