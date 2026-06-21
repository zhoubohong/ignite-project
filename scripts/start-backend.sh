#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}/backend"

# Activate conda
eval "$(conda shell.bash hook)"
conda activate bansheng

echo "Starting Bansheng Backend on http://localhost:8000 ..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
