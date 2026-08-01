"""Public data privacy scanner (spec section 27). Implemented in Milestone A.

Recursively scans public output directories (``web/public/data`` and
``data/public``) for prohibited individual-level content: ``actor_login`` /
``user_login`` / ``raw_location`` fields, GitHub profile URLs, email addresses,
and API-token-looking strings. The deployment pipeline must fail when any
violation is found; ``codetalent validate all`` runs this scan as a real stage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PUBLIC_DIRS: tuple[Path, ...] = (Path("web/public/data"), Path("data/public"))

_SCANNED_SUFFIXES = {
    ".json",
    ".geojson",
    ".ndjson",
    ".jsonl",
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".yaml",
    ".yml",
    ".html",
    ".js",
    ".xml",
}

_EXCERPT_LIMIT = 120

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("actor_login field", re.compile(r"\bactor_login\b")),
    ("user_login field", re.compile(r"\buser_login\b")),
    ("raw_location field", re.compile(r"\braw_location\b")),
    (
        # A profile URL is github.com/<login> with no further path segment.
        "github profile URL",
        re.compile(r"https?://(?:www\.)?github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]*)/?(?![\w/-])"),
    ),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("API token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
)


@dataclass(frozen=True)
class PrivacyViolation:
    """One prohibited pattern found in a public data file."""

    file: Path
    pattern: str
    excerpt: str


def _excerpt(line: str) -> str:
    stripped = line.strip()
    return stripped if len(stripped) <= _EXCERPT_LIMIT else stripped[:_EXCERPT_LIMIT] + "…"


def scan_file(path: Path) -> list[PrivacyViolation]:
    """Scan one text file for every prohibited pattern."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []  # binary asset (e.g. an image); nothing text-like to leak
    violations: list[PrivacyViolation] = []
    for line in text.splitlines():
        violations.extend(
            PrivacyViolation(file=path, pattern=name, excerpt=_excerpt(line))
            for name, pattern in _PATTERNS
            if pattern.search(line)
        )
    return violations


def scan_public_data(directories: tuple[Path, ...] = DEFAULT_PUBLIC_DIRS) -> list[PrivacyViolation]:
    """Recursively scan the given directories; return all violations found.

    Missing directories are skipped (nothing published means nothing leaked).
    Hidden files such as ``.gitkeep`` are ignored; every scannable text file is
    checked.
    """
    violations: list[PrivacyViolation] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in _SCANNED_SUFFIXES and path.suffix != "":
                continue
            violations.extend(scan_file(path))
    return violations
