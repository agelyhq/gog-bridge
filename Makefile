.PHONY: install build check lint format test e2e run clean

install:
	uv sync --all-extras

build:
	uv build

# What CI runs, and what to run before pushing. ci.yml spells these recipes
# out as uv commands because make is not guaranteed on the Windows runner.
check: lint test

lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy

format:
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts

test:
	uv run pytest

# The end-to-end tier: the installed console script over stdio against the
# real gog v0.40.0, downloaded once into .cache/gog/ and SHA256-checked.
e2e:
	GOG_BRIDGE_E2E_GOG=$$(uv run python scripts/fetch_gog.py) uv run pytest -m e2e -v

run:
	uv run gog-bridge

clean:
	rm -rf dist .pytest_cache .ruff_cache .mypy_cache
	find src tests -name __pycache__ -type d -exec rm -rf {} +
