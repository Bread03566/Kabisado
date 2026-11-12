#!/usr/bin/env bash
# Run the backend tests (SQLite) in Docker. Usage: bash backend/scripts/test.sh [pytest args]
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -q -t kabisado-backend-test -f Dockerfile.test . >/dev/null
MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD":/app -w /app kabisado-backend-test python -m pytest "$@"
