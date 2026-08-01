#!/usr/bin/env python3
"""Wrapper for user profile enrichment. The CLI is the real entry point (Milestone D)."""

from __future__ import annotations


def main() -> None:
    print(
        "User profile enrichment runs through the CLI once Milestone D lands:\n"
        "  uv run codetalent github enrich-users --input data/interim/contributors.parquet"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
