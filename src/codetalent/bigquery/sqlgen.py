"""SQL template loading, strict rendering, and audited fragment builders.

Templates live in ``sql/`` and use named ``{snake_case}`` placeholders plus
``-- statement: <name>`` delimiters (convention documented at the top of
``sql/00_profile_tables.sql``). Rendering is strict: missing parameters,
unused parameters, and duplicate statement names are all errors.

Injection safety: identifiers are validated against conservative character
classes, every string literal passes through :func:`sql_string_literal`, and
regular expressions are emitted as BigQuery raw strings after validation. All
scoring weights and thresholds are rendered from the configuration contracts —
no scoring or threshold number is hardcoded in SQL or here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from codetalent.config import BotPatternsConfig, EventWeights, TaxonomyConfig

DEFAULT_SQL_DIR = Path("sql")

GRID_TABLE_FORMAT = "events_grid_{month}"
HUMAN_GRID_VIEW = "events_grid_human"
BOT_AUDIT_TABLE = "bot_exclusion_audit"
REPO_ACTIVITY_TABLE_FORMAT = "repo_activity_{domain_id}"
REPO_DISCOVERY_TABLE_FORMAT = "repo_discovery_{domain_id}"
CONTRIBUTOR_TABLE_FORMAT = "contributor_activity_{domain_id}"

# discovery_status values written by sql/04_apply_activity_filters.sql.
STATUS_ACCEPTED = "accepted"
STATUS_EXCLUDED = "excluded"
STATUS_BELOW_FLOOR = "below_floor"
STATUS_NOT_CANDIDATE = "not_candidate"
CANDIDATE_STATUSES = (STATUS_ACCEPTED, STATUS_EXCLUDED)

_STATEMENT_MARKER = re.compile(r"^--\s*statement:\s*([a-z0-9_]+)\s*$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)\}")
# GCP project ids allow lowercase letters, digits, and hyphens; datasets and
# tables allow letters, digits, and underscores. One conservative superset.
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")
_MONTH = re.compile(r"^\d{6}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The full explicit column list of a month grid table, in materialized order.
GRID_COLUMNS: tuple[str, ...] = (
    "repo_name",
    "actor_login",
    "month",
    "is_bot",
    "bot_pattern",
    "push_events",
    "push_commit_count",
    "prs_opened",
    "prs_closed",
    "prs_merged",
    "reviews_submitted",
    "issues_opened",
    "issue_comments",
    "releases",
    "active_days",
    "active_day_mask",
    "first_seen",
    "last_seen",
)

# Minimum taxonomy term length kept for name matching; shorter fragments are
# too ambiguous to match repository names against.
MIN_TAXONOMY_TERM_LENGTH = 3


class SqlRenderError(ValueError):
    """Raised for template, placeholder, or escaping problems."""


def load_statements(template_path: Path) -> dict[str, str]:
    """Parse one template file into ordered ``{statement_name: sql}``."""
    if not template_path.is_file():
        raise SqlRenderError(f"missing SQL template: {template_path}")
    text = template_path.read_text(encoding="utf-8")
    markers = list(_STATEMENT_MARKER.finditer(text))
    if not markers:
        raise SqlRenderError(f"{template_path}: no '-- statement: <name>' marker found")
    statements: dict[str, str] = {}
    for index, marker in enumerate(markers):
        name = marker.group(1)
        if name in statements:
            raise SqlRenderError(f"{template_path}: duplicate statement name {name!r}")
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[marker.end() : end].strip()
        if not body:
            raise SqlRenderError(f"{template_path}: statement {name!r} is empty")
        statements[name] = body
    return statements


def render_statement(sql_template: str, params: Mapping[str, str]) -> str:
    """Substitute every ``{placeholder}`` strictly, in a single pass.

    Every placeholder in the template must have a parameter and every parameter
    must be used; both directions failing loudly catches template drift.
    Substituted values are never re-scanned for placeholders.
    """
    found = set(_PLACEHOLDER.findall(sql_template))
    provided = set(params)
    missing = found - provided
    if missing:
        raise SqlRenderError(f"unrendered placeholders: {sorted(missing)}")
    unused = provided - found
    if unused:
        raise SqlRenderError(f"unused render parameters: {sorted(unused)}")
    return _PLACEHOLDER.sub(lambda match: params[match.group(1)], sql_template)


def validate_identifier(name: str, *, kind: str = "identifier") -> str:
    """Validate a BigQuery project/dataset/table identifier component."""
    if not _IDENTIFIER.fullmatch(name):
        raise SqlRenderError(f"invalid {kind}: {name!r}")
    return name


def validate_month(month: str) -> str:
    """Validate a GH Archive month-table suffix (YYYYMM)."""
    if not _MONTH.fullmatch(month):
        raise SqlRenderError(f"invalid GH Archive month suffix: {month!r}")
    return month


def validate_iso_date(value: str, *, kind: str = "date") -> str:
    """Validate a YYYY-MM-DD date string destined for a SQL DATE literal."""
    if not _ISO_DATE.fullmatch(value):
        raise SqlRenderError(f"invalid {kind}: {value!r} (expected YYYY-MM-DD)")
    return value


def sql_string_literal(value: str) -> str:
    """Escape a Python string into a single-quoted BigQuery string literal."""
    if any(ord(char) < 32 for char in value):
        raise SqlRenderError(f"control characters not allowed in SQL literal: {value!r}")
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def sql_raw_regex_literal(pattern: str) -> str:
    """Emit a BigQuery raw string literal (``r'...'``) for a regex pattern.

    Raw strings cannot escape quotes, so patterns containing a single quote are
    rejected rather than silently mangled. The pattern must also compile.
    """
    if "'" in pattern:
        raise SqlRenderError(f"single quotes not allowed in regex patterns: {pattern!r}")
    if any(ord(char) < 32 for char in pattern):
        raise SqlRenderError(f"control characters not allowed in regex patterns: {pattern!r}")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise SqlRenderError(f"regex pattern does not compile: {pattern!r}: {exc}") from exc
    return f"r'{pattern}'"


def sql_number(value: float) -> str:
    """Render a config number as a SQL literal."""
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise SqlRenderError(f"non-finite number cannot be rendered: {value!r}")
    return repr(int(number)) if number.is_integer() else repr(number)


def bot_pattern_case(patterns: BotPatternsConfig, *, column: str = "actor_login") -> str:
    """CASE expression labeling the first matching bot pattern, else NULL.

    Branch order (suffixes, exact logins, substrings, regexes) is deterministic
    and follows the config file layout. Labels are ``<kind>:<pattern>`` so the
    audit table records excluded counts by pattern (spec section 13). Matching
    is case-insensitive: logins are lowercased before comparison, so the config
    patterns (including the ``[bot]`` suffix) are matched against lowercase.
    """
    branches: list[str] = []
    for suffix in patterns.login_suffixes:
        literal = sql_string_literal(suffix.lower())
        label = sql_string_literal(f"login_suffix:{suffix}")
        branches.append(f"WHEN ENDS_WITH(LOWER({column}), {literal}) THEN {label}")
    for login in patterns.exact_logins:
        literal = sql_string_literal(login.lower())
        label = sql_string_literal(f"exact_login:{login}")
        branches.append(f"WHEN LOWER({column}) = {literal} THEN {label}")
    for substring in patterns.substring_patterns:
        literal = sql_string_literal(substring.lower())
        label = sql_string_literal(f"substring:{substring}")
        branches.append(f"WHEN STRPOS(LOWER({column}), {literal}) > 0 THEN {label}")
    for regex in patterns.regex_patterns:
        literal = sql_raw_regex_literal(regex)
        label = sql_string_literal(f"regex:{regex}")
        branches.append(f"WHEN REGEXP_CONTAINS(LOWER({column}), {literal}) THEN {label}")
    joined = "\n      ".join(branches)
    return f"CASE\n      {joined}\n      ELSE NULL\n    END"


def taxonomy_name_terms(taxonomy: TaxonomyConfig) -> list[str]:
    """Normalized name-matching terms from positive topics and terms.

    Each source string is lowercased and stripped; multi-word terms produce a
    hyphenated and a concatenated variant because repository names cannot
    contain spaces. Fragments shorter than MIN_TAXONOMY_TERM_LENGTH are
    dropped. Sorted and de-duplicated for deterministic SQL.
    """
    variants: set[str] = set()
    for subdomain in taxonomy.subdomains.values():
        for source in (*subdomain.positive_topics, *subdomain.positive_terms):
            base = source.strip().lower()
            if not base:
                continue
            for variant in (base.replace(" ", "-"), base.replace(" ", "")):
                if len(variant) >= MIN_TAXONOMY_TERM_LENGTH:
                    variants.add(variant)
    return sorted(variants)


def taxonomy_match_predicate(taxonomy: TaxonomyConfig, *, column: str = "repo_name") -> str:
    """Boolean SQL predicate: does the repo name match any taxonomy term?

    Terms must be bounded by a non-alphanumeric character or the string edge,
    so ``salt`` does not match ``basalt`` while ``terraform`` still matches
    ``owner/terraform-provider-foo``. Name-only matching is recall-limited by
    design (documented tradeoff); Milestone C refines with topics/descriptions.
    """
    terms = taxonomy_name_terms(taxonomy)
    if not terms:
        raise SqlRenderError(f"taxonomy {taxonomy.domain_id!r} produced no name terms")
    alternation = "|".join(re.escape(term) for term in terms)
    pattern = f"(^|[^a-z0-9])({alternation})($|[^a-z0-9])"
    return f"REGEXP_CONTAINS(LOWER({column}), {sql_raw_regex_literal(pattern)})"


def grid_table_id(project: str, dataset: str, month: str) -> str:
    """Fully qualified month grid table id."""
    validate_identifier(project, kind="project")
    validate_identifier(dataset, kind="dataset")
    validate_month(month)
    return f"{project}.{dataset}.{GRID_TABLE_FORMAT.format(month=month)}"


def grid_union(project: str, dataset: str, months: list[str]) -> str:
    """UNION ALL over the month grid tables with the explicit column list."""
    if not months:
        raise SqlRenderError("grid_union requires at least one month")
    column_list = ", ".join(GRID_COLUMNS)
    selects = [
        f"  SELECT {column_list}\n  FROM `{grid_table_id(project, dataset, month)}`"
        for month in months
    ]
    return "\n  UNION ALL\n".join(selects)


def grid_duplicate_total(project: str, dataset: str, months: list[str]) -> str:
    """Fragment summing duplicate (repo_name, actor_login) counts per grid."""
    if not months:
        raise SqlRenderError("grid_duplicate_total requires at least one month")
    subqueries = [
        "(\n      SELECT COUNT(*)\n      FROM (\n"
        "        SELECT repo_name, actor_login\n"
        f"        FROM `{grid_table_id(project, dataset, month)}`\n"
        "        GROUP BY repo_name, actor_login\n"
        "        HAVING COUNT(*) > 1\n      )\n    )"
        for month in months
    ]
    return "\n    + ".join(subqueries)


def event_weight_params(weights: EventWeights) -> dict[str, str]:
    """Render config/scoring.yaml event weights as SQL number parameters."""
    return {
        "weight_merged_pull_request": sql_number(weights.merged_pull_request),
        "weight_pull_request_review": sql_number(weights.pull_request_review),
        "weight_pull_request_opened": sql_number(weights.pull_request_opened),
        "weight_release": sql_number(weights.release),
        "weight_push_event": sql_number(weights.push_event),
        "weight_issue_opened": sql_number(weights.issue_opened),
        "weight_issue_comment": sql_number(weights.issue_comment),
    }
