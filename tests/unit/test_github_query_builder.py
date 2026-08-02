"""Query builder tests: aliases, spec 9.2 field coverage, content-presence signals."""

from __future__ import annotations

import re

import pytest

from codetalent.github.query_builder import (
    REPO_QUERY_VERSION,
    build_repository_batch_query,
    repo_alias,
)

REPOS = [
    "kubernetes/kubernetes",
    "grafana/grafana.github.io",
    "hashicorp/terraform-provider-aws",
]

SPEC_92_SNIPPETS = [
    "isFork",
    "isArchived",
    "isDisabled",
    "description",
    "primaryLanguage { name }",
    "repositoryTopics(first: 20) { nodes { topic { name } } }",
    "stargazerCount",
    "forkCount",
    "licenseInfo { spdxId }",
    "pushedAt",
    "updatedAt",
    "releases { totalCount }",
    "issues { totalCount }",
    "pullRequests { totalCount }",
]

CONTENT_EXPRESSIONS = [
    "HEAD:README.md",
    "HEAD:README.rst",
    "HEAD:readme.md",
    "HEAD:CONTRIBUTING.md",
    "HEAD:CODE_OF_CONDUCT.md",
    "HEAD:.github/workflows",
    "HEAD:tests",
    "HEAD:test",
]

_VALID_ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TestBuildRepositoryBatchQuery:
    def test_all_spec_92_fields_requested(self) -> None:
        built = build_repository_batch_query(REPOS)
        for snippet in SPEC_92_SNIPPETS:
            assert snippet in built.query, snippet

    def test_all_content_presence_expressions_present(self) -> None:
        built = build_repository_batch_query(REPOS)
        for expression in CONTENT_EXPRESSIONS:
            assert f'object(expression: "{expression}")' in built.query, expression

    def test_rate_limit_block_always_requested(self) -> None:
        built = build_repository_batch_query(REPOS)
        assert "rateLimit { limit cost remaining resetAt }" in built.query

    def test_aliases_are_valid_graphql_identifiers(self) -> None:
        built = build_repository_batch_query(REPOS)
        assert list(built.alias_to_repo) == ["r0", "r1", "r2"]
        for alias in built.alias_to_repo:
            assert _VALID_ALIAS.match(alias)

    def test_alias_map_round_trips_repo_names_with_dashes_and_dots(self) -> None:
        built = build_repository_batch_query(REPOS)
        assert built.alias_to_repo == {repo_alias(i): name for i, name in enumerate(sorted(REPOS))}
        for alias, full_name in built.alias_to_repo.items():
            owner, name = full_name.split("/", 1)
            assert f'{alias}: repository(owner: "{owner}", name: "{name}")' in built.query

    def test_aliases_are_assigned_in_sorted_order_regardless_of_input_order(self) -> None:
        # The response cache key is order-insensitive, so alias attribution
        # must be too: any ordering of the same batch yields identical aliases,
        # or a cache hit would attach metadata to the wrong repo_name.
        shuffled = build_repository_batch_query(list(reversed(REPOS)))
        canonical = build_repository_batch_query(sorted(REPOS))
        assert shuffled.alias_to_repo == canonical.alias_to_repo
        assert shuffled.query == canonical.query

    def test_each_alias_spreads_the_shared_fragment(self) -> None:
        built = build_repository_batch_query(REPOS)
        assert built.query.count("...RepoEnrichmentFields") == len(REPOS)
        assert "fragment RepoEnrichmentFields on Repository" in built.query

    def test_empty_batch_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            build_repository_batch_query([])

    @pytest.mark.parametrize(
        "bad_name",
        ["no-slash", "owner/name/extra", 'owner/na"me', "owner/na me", "", "owner/"],
    )
    def test_invalid_repository_names_rejected(self, bad_name: str) -> None:
        with pytest.raises(ValueError, match="invalid repository name"):
            build_repository_batch_query([bad_name])

    def test_query_version_constant_exists_for_cache_busting(self) -> None:
        assert REPO_QUERY_VERSION
        assert isinstance(REPO_QUERY_VERSION, str)
