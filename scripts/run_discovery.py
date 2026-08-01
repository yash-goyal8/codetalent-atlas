#!/usr/bin/env python3
"""Wrapper for GH Archive discovery. The CLI is the real entry point (Milestone B)."""

from __future__ import annotations


def main() -> None:
    print(
        "Repository discovery runs through the CLI once Milestone B lands:\n"
        "  uv run codetalent bq dry-run --start 2026-05-01 --end 2026-07-31\n"
        "  uv run codetalent bq discover --domain cloud_devops "
        "--start 2026-05-01 --end 2026-07-31"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
