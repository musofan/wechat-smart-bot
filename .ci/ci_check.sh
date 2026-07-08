#!/usr/bin/env bash
# Local pre-commit gate. Cline MUST run this and see it pass before every commit.
# Same checks the CI monitor and GitHub Actions run.
set -e
PY="${PYTHON:-C:/Users/Tung/AppData/Local/Python/pythoncore-3.12-64/python.exe}"
echo ">> ruff"
"$PY" -m ruff check .
echo ">> pytest (mock suite)"
"$PY" -m pytest
echo ">> OK: green. Safe to commit."
