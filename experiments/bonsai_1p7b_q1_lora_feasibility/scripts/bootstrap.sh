#!/usr/bin/env bash
set -euo pipefail
: "${OUTPUT_ROOT:?Set OUTPUT_ROOT}"
python3.11 -m venv "${OUTPUT_ROOT}/.venv"
"${OUTPUT_ROOT}/.venv/bin/python" -m pip install --upgrade pip
"${OUTPUT_ROOT}/.venv/bin/python" -m pip install -e ".[test]"
"${OUTPUT_ROOT}/.venv/bin/python" -m pip freeze

