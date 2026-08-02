"""Response cache keyed by normalized request hash (spec section 14).

Every external response is cached under ``data/cache/github/`` (gitignored) so
runs are deterministic and rerunnable without duplicate API calls. Repository
batch hashes cover the *sorted* repository list plus the query-shape version
constant (:data:`codetalent.github.query_builder.REPO_QUERY_VERSION`); bumping
that constant invalidates every previously cached response.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def request_hash(payload: Mapping[str, Any]) -> str:
    """Stable SHA-256 over the canonical (sorted-keys) JSON form of a payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def repository_batch_hash(repo_names: Iterable[str], *, query_version: str) -> str:
    """Hash for one repository batch: sorted repo list + query version constant.

    Order-insensitive by design, which is only safe because
    :func:`codetalent.github.query_builder.build_repository_batch_query`
    likewise sorts before assigning positional aliases — the cached payload's
    alias attribution is thus identical for every ordering of the same batch.
    """
    return request_hash(
        {
            "kind": "github-graphql-repositories",
            "version": query_version,
            "repos": sorted(repo_names),
        }
    )


class ResponseCache:
    """Filesystem cache: ``<root>/<hash>.json`` with atomic writes."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        """Return the cached response for a request hash, or None on a miss.

        A corrupt cache file (interrupted write from a crashed run) is treated
        as a miss so the record is simply refetched.
        """
        path = self.path_for(key)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def put(self, key: str, response: Mapping[str, Any]) -> None:
        """Store one response payload atomically (temp file + rename)."""
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(key)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(response, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
