"""Alias-based batched GraphQL query generation (spec sections 9.2 and 14).

Each batch fetches, per repository, exactly the spec 9.2 metadata fields plus
one-pass content-presence signals via ``object(expression:)`` lookups (these
resolve README/CONTRIBUTING/CODE_OF_CONDUCT/CI/tests existence in the same
request, so no per-repository REST call is needed):

* ``has_readme`` — ``HEAD:README.md`` OR ``HEAD:README.rst`` OR
  ``HEAD:readme.md`` (three aliases; ``object`` lookups are not connections, so
  the extra variants do not change the query's rate-limit cost).
* ``has_contributing`` — ``HEAD:CONTRIBUTING.md``
* ``has_code_of_conduct`` — ``HEAD:CODE_OF_CONDUCT.md``
* ``has_ci`` — ``HEAD:.github/workflows``
* ``has_tests_signal`` — ``HEAD:tests`` OR ``HEAD:test``

Repository names may contain dashes and dots, which are invalid in GraphQL
alias identifiers, so aliases are positional (``r0``, ``r1``, ...) and each
query carries an alias -> ``owner/name`` map for response parsing.

Bump :data:`REPO_QUERY_VERSION` whenever the query shape changes — it is part
of the response-cache request hash, so a bump invalidates stale cached shapes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

#: Cache-busting version of the repository query shape (see module docstring).
REPO_QUERY_VERSION = "repo-enrichment-v1"
#: Version for the content-signal-free bulk variant (separate cache namespace).
REPO_QUERY_VERSION_LIGHT = "repo-enrichment-v1-light"

#: Conservative owner/name charset; also guards against GraphQL injection
#: because quotes and backslashes can never appear in a valid repo name.
_REPO_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")

_REPO_BASE_FIELDS = """\
  nameWithOwner
  isFork
  isArchived
  isDisabled
  description
  primaryLanguage { name }
  repositoryTopics(first: 20) { nodes { topic { name } } }
  stargazerCount
  forkCount
  licenseInfo { spdxId }
  pushedAt
  updatedAt
  releases { totalCount }
  issues { totalCount }
  pullRequests { totalCount }"""

# git object() lookups are server-expensive (~10 per repo made 25-repo batches
# take ~30s); the spec limits content checks to a small shortlist, so the bulk
# pass omits them and a second pass covers classified-qualified repos only.
_REPO_CONTENT_SIGNAL_FIELDS = """\
  readmeMd: object(expression: "HEAD:README.md") { __typename }
  readmeRst: object(expression: "HEAD:README.rst") { __typename }
  readmeLower: object(expression: "HEAD:readme.md") { __typename }
  contributing: object(expression: "HEAD:CONTRIBUTING.md") { __typename }
  codeOfConduct: object(expression: "HEAD:CODE_OF_CONDUCT.md") { __typename }
  ciWorkflows: object(expression: "HEAD:.github/workflows") { __typename }
  testsDir: object(expression: "HEAD:tests") { __typename }
  testDir: object(expression: "HEAD:test") { __typename }"""

_REPO_FIELDS_FRAGMENT = (
    "fragment RepoEnrichmentFields on Repository {\n"
    + _REPO_BASE_FIELDS
    + "\n"
    + _REPO_CONTENT_SIGNAL_FIELDS
    + "\n}"
)

_REPO_FIELDS_FRAGMENT_LIGHT = (
    "fragment RepoEnrichmentFields on Repository {\n" + _REPO_BASE_FIELDS + "\n}"
)


@dataclass(frozen=True)
class RepositoryBatchQuery:
    """One rendered batch query plus its alias -> ``owner/name`` map."""

    query: str
    alias_to_repo: dict[str, str]


def repo_alias(index: int) -> str:
    """Positional alias for the repository at ``index`` within a batch."""
    return f"r{index}"


def build_repository_batch_query(
    repo_names: Sequence[str], *, include_content_signals: bool = True
) -> RepositoryBatchQuery:
    """Build one aliased GraphQL query fetching spec 9.2 metadata for each repository.

    The query always requests the ``rateLimit`` block so every response reports
    its cost and remaining budget (API-safety rule 1).

    Repositories are **sorted (and deduplicated) before alias assignment**, so
    the alias map always corresponds to the sorted batch. This is a correctness
    invariant, not a cosmetic choice: the response cache key
    (:func:`codetalent.github.cache.repository_batch_hash`) is order-insensitive,
    so two callers passing the same repositories in different orders share one
    cached payload — aliases must therefore be attributed identically for both,
    or a cache hit would silently attach every repository's metadata to the
    wrong ``repo_name``. Callers must read alias attribution from the returned
    ``alias_to_repo`` map, never from their own input order.
    """
    if not repo_names:
        raise ValueError("repo_names must not be empty")

    lines = [
        "query RepositoryEnrichmentBatch {",
        "  rateLimit { limit cost remaining resetAt }",
    ]
    alias_to_repo: dict[str, str] = {}
    for index, full_name in enumerate(sorted(set(repo_names))):
        if not _REPO_NAME_RE.match(full_name):
            raise ValueError(f"invalid repository name: {full_name!r} (expected owner/name)")
        owner, name = full_name.split("/", 1)
        alias = repo_alias(index)
        alias_to_repo[alias] = full_name
        lines.append(
            f'  {alias}: repository(owner: "{owner}", name: "{name}") {{ ...RepoEnrichmentFields }}'
        )
    lines.append("}")
    fragment = _REPO_FIELDS_FRAGMENT if include_content_signals else _REPO_FIELDS_FRAGMENT_LIGHT
    query = "\n".join(lines) + "\n" + fragment
    return RepositoryBatchQuery(query=query, alias_to_repo=alias_to_repo)


def build_user_batch_query(logins: list[str]) -> str:
    """Build one aliased GraphQL query fetching spec 9.5 profile fields for each login."""
    raise NotImplementedError("Milestone D implements user query building.")
