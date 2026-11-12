#!/usr/bin/env bash
# Runs the local Phase 0 tests in throwaway containers. Needs Docker. Touches nothing outside Docker.
set -euo pipefail
cd "$(dirname "$0")/.."
docker network create p0net >/dev/null 2>&1 || true
docker rm -f p0pg >/dev/null 2>&1 || true
docker run -d --name p0pg --network p0net -e POSTGRES_PASSWORD=pw postgres:16 >/dev/null
docker build -q -t p0runner -f local/Dockerfile.runner . >/dev/null
for i in $(seq 1 40); do docker exec p0pg pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
sleep 3
rc=0
MSYS_NO_PATHCONV=1 docker run --rm --network p0net -e PGHOST=p0pg -e PGPASSWORD=pw -v "$PWD":/work p0runner python /work/local/test_local.py || rc=$?
docker rm -f p0pg >/dev/null; docker network rm p0net >/dev/null
exit $rc
