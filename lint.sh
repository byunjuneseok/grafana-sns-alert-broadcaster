#!/bin/bash
set -e

echo "Running ruff format..."
uv run ruff format app tests

echo "Running ruff check --fix..."
uv run ruff check --fix app tests

echo "Done."
