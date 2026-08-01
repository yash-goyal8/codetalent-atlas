#!/usr/bin/env python3
"""Wrapper for the static web data build. The CLI is the real entry point (Milestone F)."""

from __future__ import annotations


def main() -> None:
    print(
        "The aggregate-only web data build runs through the CLI once Milestone F lands:\n"
        "  uv run codetalent publish web-data"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
