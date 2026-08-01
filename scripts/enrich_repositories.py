#!/usr/bin/env python3
"""Wrapper for repository enrichment. The CLI is the real entry point (Milestone C)."""

from __future__ import annotations


def main() -> None:
    print(
        "Repository enrichment runs through the CLI once Milestone C lands:\n"
        "  uv run codetalent github enrich-repos --input data/interim/candidates.parquet"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
