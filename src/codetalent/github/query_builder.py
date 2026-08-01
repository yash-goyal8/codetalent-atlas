"""Alias-based GraphQL query generation (spec section 14).

Builds batched repository and user queries starting at 10 items per request,
adapting batch size only after measuring query cost. Target milestones:
C (repositories), D (users).
"""

from __future__ import annotations


def build_repository_batch_query(repo_names: list[str]) -> str:
    """Build one aliased GraphQL query fetching spec 9.2 metadata for each repository."""
    raise NotImplementedError("Milestone C implements repository query building.")


def build_user_batch_query(logins: list[str]) -> str:
    """Build one aliased GraphQL query fetching spec 9.5 profile fields for each login."""
    raise NotImplementedError("Milestone D implements user query building.")
