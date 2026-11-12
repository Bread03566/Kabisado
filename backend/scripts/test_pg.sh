#!/usr/bin/env bash
# Run the backend tests against a throwaway Postgres 17 (schema from Alembic). Usage: bash backend/scripts/test_pg.sh [pytest args]
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -q -t kabisado-backend-test -f Dockerfile.test . >/dev/null
docker network create kab-pgnet >/dev/null 2>&1 || true
docker rm -f kab-pg >/dev/null 2>&1 || true
docker run -d --name kab-pg --network kab-pgnet -e POSTGRES_PASSWORD=pw postgres:17 >/dev/null
cleanup() { docker rm -f kab-pg >/dev/null 2>&1; docker network rm kab-pgnet >/dev/null 2>&1; }
trap cleanup EXIT
for i in $(seq 1 40); do docker exec kab-pg pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
sleep 2
export MSYS_NO_PATHCONV=1
docker run --rm --network kab-pgnet -v "$PWD":/app -w /app \
  -e DATABASE_URL=postgresql://postgres:pw@kab-pg:5432/postgres -e AUTO_CREATE_SCHEMA=false \
  kabisado-backend-test sh -c 'if [ -f alembic.ini ]; then alembic upgrade head; fi && python -m pytest "$@"' sh "$@"
