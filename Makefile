# CodeTalent Atlas developer entry points.
# Thin wrappers over the canonical commands documented in README.md and AGENTS.md.
# Recipes are echoed by make as they run, so each target shows exactly what it executes.

.PHONY: setup lint format typecheck test build qa privacy-scan clean

setup:
	uv sync --all-groups
	pnpm install

lint:
	uv run ruff check .
	uv run ruff format --check .
	pnpm --dir web lint

format:
	uv run ruff format .

typecheck:
	uv run mypy src
	pnpm --dir web typecheck

test:
	uv run pytest
	pnpm --dir web test

build:
	pnpm --dir web build

qa: lint typecheck test build

privacy-scan:
	uv run pytest -k privacy

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	rm -rf web/dist web/coverage
	find src tests scripts -type d -name __pycache__ -prune -exec rm -rf {} +
