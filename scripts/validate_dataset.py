#!/usr/bin/env python3
"""Wrapper for dataset validation. Config validation and the privacy scan already run today."""

from __future__ import annotations


def main() -> None:
    print(
        "Validation runs through the CLI (config validation and the public-data privacy\n"
        "scan are live now; the remaining stages land in Milestone E):\n"
        "  uv run codetalent validate all"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
