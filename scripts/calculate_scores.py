#!/usr/bin/env python3
"""Wrapper for scoring. The CLI is the real entry point (Milestone E)."""

from __future__ import annotations


def main() -> None:
    print(
        "Scoring runs through the CLI once Milestone E lands:\n"
        "  uv run codetalent score repositories\n"
        "  uv run codetalent score contributors\n"
        "  uv run codetalent score geographies"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
