"""Deterministic repository taxonomy classification (spec section 12). Milestone C.

Public entry point for pipeline wiring:
``codetalent.classify.runner.classify_repositories``.
"""

from codetalent.classify.runner import ClassificationRunSummary, classify_repositories

__all__ = ["ClassificationRunSummary", "classify_repositories"]
