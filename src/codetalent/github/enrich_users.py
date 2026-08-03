"""Resumable, cache-first public user-profile enrichment (spec 9.5 / 14).

Mirrors the repository orchestrator: checkpointed worklist, request-hash
cache, ledger row per request, bisection on whole-request failures, atomic
dedup parquet writes. Fetches ONLY login, account type, public location,
creation date, and followers count — never emails, names, employers, or
websites. Output stays under gitignored ``data/interim/``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from codetalent.github.cache import ResponseCache, repository_batch_hash
from codetalent.github.checkpoints import CheckpointStore
from codetalent.github.enrich_repos import (
    INITIAL_BATCH_SIZE,
    STATUS_AUTH_ERROR,
    STATUS_ERROR,
    STATUS_SUCCESS,
    EnrichmentReport,
    EnrichmentUsageLedger,
    WorklistError,
    next_batch_size,
)
from codetalent.github.graphql_client import (
    TOKEN_SETUP_INSTRUCTIONS,
    GitHubAuthenticationError,
    GraphQLClient,
    GraphQLRequestError,
)
from codetalent.github.query_builder import USER_QUERY_VERSION, build_user_batch_query
from codetalent.github.rate_limit import DEFAULT_RATE_LIMIT_FLOOR
from codetalent.runlog import RunLogger
from codetalent.schemas import AccountType, FetchStatus, UserProfile
from codetalent.settings import Settings, load_settings

DEFAULT_ACTIVITY_PATH = Path("data/interim/contributor_activity.parquet")
DEFAULT_QUALIFIED_PATH = Path("data/interim/repository_classification.parquet")
PROFILES_PATH = Path("data/interim/user_profiles.parquet")
USER_CHECKPOINT_PATH = Path("data/interim/checkpoints/users.json")
USER_CACHE_DIR = Path("data/cache/github/graphql/users")
RESOURCE_TYPE_USERS = "graphql_users"

_PROFILE_SCHEMA: dict[str, pl.DataType] = {
    "actor_login": pl.String(),
    "account_type": pl.String(),
    "public_location_raw": pl.String(),
    "created_at": pl.Datetime(time_unit="us", time_zone="UTC"),
    "followers_count": pl.Int64(),
    "profile_fetched_at": pl.Datetime(time_unit="us", time_zone="UTC"),
    "fetch_status": pl.String(),
}


def load_user_worklist(
    activity_path: Path = DEFAULT_ACTIVITY_PATH,
    qualified_path: Path | None = DEFAULT_QUALIFIED_PATH,
) -> list[str]:
    """Distinct contributor logins, restricted to classified-qualified repos.

    Falls back (loudly, via the returned size) to all contributor actors when
    the classification parquet does not exist yet.
    """
    if not activity_path.exists():
        raise WorklistError(
            f"worklist not found: {activity_path} — run `codetalent bq discover` first"
        )
    activity = pl.read_parquet(activity_path, columns=["actor_login", "repo_name"])
    if qualified_path is not None and qualified_path.exists():
        qualified = (
            pl.read_parquet(qualified_path, columns=["repo_name", "classification_status"])
            .filter(pl.col("classification_status") == "accepted")
            .get_column("repo_name")
        )
        activity = activity.filter(pl.col("repo_name").is_in(qualified.implode()))
    return sorted(set(activity.get_column("actor_login").to_list()))


def profile_from_node(login: str, node: dict[str, Any] | None, fetched_at: datetime) -> UserProfile:
    """Map one repositoryOwner node (or null = deleted) to a spec 9.5 row."""
    if node is None:
        return UserProfile(
            actor_login=login,
            account_type=AccountType.UNKNOWN,
            profile_fetched_at=fetched_at,
            fetch_status=FetchStatus.NOT_FOUND,
        )
    typename = node.get("__typename")
    if typename == "Organization":
        return UserProfile(
            actor_login=login,
            account_type=AccountType.ORGANIZATION,
            profile_fetched_at=fetched_at,
            fetch_status=FetchStatus.SUCCESS,
        )
    created_raw = node.get("createdAt")
    created = None
    if isinstance(created_raw, str) and created_raw:
        created = datetime.fromisoformat(created_raw)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
    followers = (node.get("followers") or {}).get("totalCount")
    return UserProfile(
        actor_login=login,
        account_type=AccountType.USER if typename == "User" else AccountType.UNKNOWN,
        public_location_raw=node.get("location"),
        created_at=created,
        followers_count=int(followers) if followers is not None else None,
        profile_fetched_at=fetched_at,
        fetch_status=FetchStatus.SUCCESS,
    )


def write_profiles_atomic(rows: list[UserProfile], path: Path) -> int:
    """Merge rows into the profiles parquet atomically; return row count."""
    fresh = pl.DataFrame(
        [row.model_dump(mode="python") for row in rows],
        schema=_PROFILE_SCHEMA,
    )
    frames = [fresh]
    if path.exists():
        frames.insert(0, pl.read_parquet(path).cast(_PROFILE_SCHEMA))  # type: ignore[arg-type]
    combined = (
        pl.concat(frames)
        .sort("profile_fetched_at")
        .unique(subset=["actor_login"], keep="last", maintain_order=True)
        .sort("actor_login")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    combined.write_parquet(tmp)
    tmp.replace(path)
    return combined.height


def enrich_users(
    *,
    settings: Settings | None = None,
    activity_path: Path = DEFAULT_ACTIVITY_PATH,
    qualified_path: Path | None = DEFAULT_QUALIFIED_PATH,
    output_path: Path = PROFILES_PATH,
    checkpoint_path: Path = USER_CHECKPOINT_PATH,
    cache_dir: Path = USER_CACHE_DIR,
    usage_report_path: Path | None = None,
    limit: int | None = None,
    client: GraphQLClient | None = None,
    logger: RunLogger | None = None,
    rate_limit_floor: int = DEFAULT_RATE_LIMIT_FLOOR,
    max_error_rate: float = 0.01,
    error_rate_min_sample: int = 100,
) -> EnrichmentReport:
    """Run resumable, cache-first user-profile enrichment over the worklist."""
    log = logger if logger is not None else RunLogger("phase4-enrich-users")
    ledger = (
        EnrichmentUsageLedger(usage_report_path)
        if usage_report_path is not None
        else EnrichmentUsageLedger()
    )
    checkpoint = CheckpointStore(checkpoint_path)
    cache = ResponseCache(cache_dir)

    worklist = load_user_worklist(activity_path, qualified_path)
    completed = checkpoint.completed_ids()
    pending = [login for login in worklist if login not in completed]
    already_completed = len(worklist) - len(pending)
    if limit is not None:
        pending = pending[: max(limit, 0)]

    if client is None:
        if settings is None:
            settings = load_settings()
        token = settings.github_token
        if token is None:
            raise GitHubAuthenticationError("GITHUB_TOKEN is not set.\n" + TOKEN_SETUP_INSTRUCTIONS)
        client = GraphQLClient(token.get_secret_value(), rate_limit_floor=rate_limit_floor)
    if client.last_rate_limit is None and checkpoint.last_rate_limit is not None:
        client.last_rate_limit = checkpoint.last_rate_limit

    batch_size = checkpoint.batch_size or INITIAL_BATCH_SIZE
    attempted = succeeded = failed = cache_hits = 0
    unexpected_failures = 0
    total_rows = 0

    log.step("worklist", "completed", records_in=len(worklist), records_out=len(pending))

    try:
        while pending:
            batch = pending[:batch_size]
            pending = pending[batch_size:]
            built = build_user_batch_query(batch)
            batch_hash = repository_batch_hash(batch, query_version=USER_QUERY_VERSION)

            cached = cache.get(batch_hash)
            cache_hit = cached is not None
            if cached is not None:
                data: dict[str, Any] = cached.get("data") or {}
                cost: int | None = 0
                response_bytes = 0
                retries = 0
                rate_state = client.last_rate_limit
                cache_hits += 1
            else:
                try:
                    result = client.execute(built.query)
                except GitHubAuthenticationError:
                    ledger.append(
                        resource_type=RESOURCE_TYPE_USERS,
                        batch_size=len(batch),
                        query_cost=0,
                        remaining=None,
                        reset_at="",
                        status=STATUS_AUTH_ERROR,
                        retries=0,
                        cache_hit=False,
                    )
                    raise
                except GraphQLRequestError as exc:
                    ledger.append(
                        resource_type=RESOURCE_TYPE_USERS,
                        batch_size=len(batch),
                        query_cost=0,
                        remaining=None,
                        reset_at="",
                        status=STATUS_ERROR,
                        retries=exc.retries,
                        cache_hit=False,
                    )
                    if len(batch) > 1:
                        # Bisect toward the poison login; count only singletons.
                        pending = batch + pending
                        batch_size = max(1, len(batch) // 2)
                        log.step("enrich-users-batch", "bisect", records_in=len(batch))
                        continue
                    checkpoint.record_batch(
                        [],
                        dict.fromkeys(batch, f"REQUEST_ERROR:{type(exc).__name__}"),
                        batch_size=batch_size,
                    )
                    attempted += 1
                    failed += 1
                    unexpected_failures += 1
                    if (
                        attempted >= error_rate_min_sample
                        and unexpected_failures / attempted > max_error_rate
                    ):
                        raise
                    continue
                data = result.data
                cost = result.rate_limit.last_cost if result.rate_limit is not None else None
                response_bytes = result.response_bytes
                retries = result.retries
                rate_state = result.rate_limit
                cache.put(batch_hash, {"data": data, "errors": result.errors})

            fetched_at = datetime.now(UTC)
            batch_rows = [
                profile_from_node(login, data.get(alias), fetched_at)
                for alias, login in built.alias_to_login.items()
            ]
            if batch_rows:
                total_rows = write_profiles_atomic(batch_rows, output_path)
            if not cache_hit:
                batch_size = next_batch_size(
                    batch_size, cost=cost, response_bytes=response_bytes, batch_len=len(batch)
                )
                rate_state_for_ledger = rate_state
                ledger.append(
                    resource_type=RESOURCE_TYPE_USERS,
                    batch_size=len(batch),
                    query_cost=cost if cost is not None else 0,
                    remaining=(
                        rate_state_for_ledger.remaining
                        if rate_state_for_ledger is not None
                        else None
                    ),
                    reset_at=(
                        rate_state_for_ledger.reset_at.isoformat()
                        if rate_state_for_ledger is not None
                        and rate_state_for_ledger.reset_at is not None
                        else ""
                    ),
                    status=STATUS_SUCCESS,
                    retries=retries,
                    cache_hit=False,
                )
            checkpoint.record_batch(
                [row.actor_login for row in batch_rows],
                {},
                rate_limit=rate_state,
                batch_size=batch_size,
            )
            attempted += len(batch)
            succeeded += len(batch_rows)
            log.step(
                "enrich-users-batch",
                "completed",
                records_in=len(batch),
                records_out=len(batch_rows),
                cache_hits=1 if cache_hit else 0,
            )
    finally:
        client.close()

    return EnrichmentReport(
        worklist_total=len(worklist),
        already_completed=already_completed,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        cache_hits=cache_hits,
        batch_size=batch_size,
        total_rows=total_rows,
        output_path=output_path,
        exhausted_failures={},
    )
