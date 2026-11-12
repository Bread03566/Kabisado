#!/usr/bin/env bash
# Phase 0 CI test: pooler connectivity from a GitHub runner, DB dump/restore, Storage upload/download/private check,
# age encryption round trip. Uses ONLY a throwaway `phase0` schema and a `phase0` bucket, removed at the end.
set -uo pipefail
: "${SUPABASE_DB_HOST:?}" "${SUPABASE_DB_USER:?}" "${SUPABASE_DB_PASSWORD:?}" "${SUPABASE_URL:?}" "${SUPABASE_SERVICE_KEY:?}"
PORT="${SUPABASE_DB_PORT:-5432}"; DB="${SUPABASE_DB_NAME:-postgres}"
OUT="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
now() { date +%s%N; }
ms() { echo $(( ($(now) - $1) / 1000000 )); }
say() { echo "$*" | tee -a "$OUT"; }
res() { say "| $1 | $2 | $3 |"; }
FAILS=0
psqlc() { docker run --rm -e PGPASSWORD="$SUPABASE_DB_PASSWORD" -e PGSSLMODE=require "$IMG" psql -h "$SUPABASE_DB_HOST" -p "$PORT" -U "$SUPABASE_DB_USER" -d "$DB" -v ON_ERROR_STOP=1 -tA "$@"; }

say "## Phase 0 CI results"
say "| Test | Result | Detail |"; say "|---|---|---|"

IMG=postgres:17
t=$(now); VER=$(psqlc -c "show server_version_num" 2>&1); rc=$?
if [ $rc -ne 0 ]; then res "pooler connect from runner (IPv4)" FAIL "$(echo "$VER" | head -c 200)"; exit 1; fi
MAJOR=$((VER / 10000)); IMG=postgres:$MAJOR
res "pooler connect from runner (session mode :$PORT)" PASS "server major $MAJOR, $(ms $t) ms incl. docker pull"

cleanup() { psqlc -c "drop schema if exists phase0 cascade" >/dev/null 2>&1; docker rm -f tgt >/dev/null 2>&1;
  curl -s -X DELETE -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" -H "apikey: $SUPABASE_SERVICE_KEY" "$SUPABASE_URL/storage/v1/object/phase0/test/file.bin" >/dev/null
  curl -s -X DELETE -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" -H "apikey: $SUPABASE_SERVICE_KEY" "$SUPABASE_URL/storage/v1/bucket/phase0" >/dev/null; }
trap cleanup EXIT

# ---- DB dump / restore ----
psqlc -c "drop schema if exists phase0 cascade; create schema phase0; create table phase0.items(id serial primary key, body text); insert into phase0.items(body) select md5(i::text) from generate_series(1,5000) i;" >/dev/null
SRC=$(psqlc -c "select count(*) from phase0.items")
t=$(now)
docker run --rm -v "$PWD:/out" -e PGPASSWORD="$SUPABASE_DB_PASSWORD" -e PGSSLMODE=require "$IMG" pg_dump -Fc -n phase0 -h "$SUPABASE_DB_HOST" -p "$PORT" -U "$SUPABASE_DB_USER" -d "$DB" -f /out/p0.dump
if [ $? -eq 0 ]; then res "pg_dump via session pooler" PASS "$(ms $t) ms, $(stat -c %s p0.dump) bytes"; else res "pg_dump via session pooler" FAIL ""; FAILS=$((FAILS+1)); fi
docker run -d --name tgt -e POSTGRES_PASSWORD=pw "$IMG" >/dev/null; sleep 8
docker run --rm --network container:tgt -v "$PWD:/out" -e PGPASSWORD=pw "$IMG" pg_restore -h localhost -U postgres -d postgres /out/p0.dump
DST=$(docker run --rm --network container:tgt -e PGPASSWORD=pw "$IMG" psql -h localhost -U postgres -tA -c "select count(*) from phase0.items")
if [ "$SRC" = "$DST" ] && [ -n "$DST" ]; then res "restore into clean Postgres" PASS "$DST rows = source"; else res "restore into clean Postgres" FAIL "src=$SRC dst=$DST"; FAILS=$((FAILS+1)); fi

# ---- age encryption round trip + artifact size ----
sudo apt-get install -y -qq age >/dev/null 2>&1
age-keygen -o key.txt 2>pub.txt; PUB=$(grep -o 'age1.*' pub.txt)
age -r "$PUB" -o p0.dump.age p0.dump && age -d -i key.txt p0.dump.age | cmp - p0.dump && res "age encrypt/decrypt dump" PASS "$(stat -c %s p0.dump.age) bytes" || { res "age encrypt/decrypt dump" FAIL ""; FAILS=$((FAILS+1)); }
head -c 40000000 /dev/urandom > big.bin; age -r "$PUB" -o big.bin.age big.bin; rm big.bin   # 40 MB incompressible artifact test file

# ---- Storage ----
H=(-H "Authorization: Bearer $SUPABASE_SERVICE_KEY" -H "apikey: $SUPABASE_SERVICE_KEY")
head -c 3000000 /dev/urandom > file.bin; SHA=$(sha256sum file.bin | cut -d' ' -f1)
code=$(curl -s -o /tmp/b.json -w '%{http_code}' -X POST "${H[@]}" -H 'Content-Type: application/json' -d '{"id":"phase0","name":"phase0","public":false}' "$SUPABASE_URL/storage/v1/bucket")
res "create private bucket" "$([ "$code" = 200 ] && echo PASS || echo FAIL)" "http $code $(head -c 120 /tmp/b.json)"
t=$(now); code=$(curl -s -o /tmp/u.json -w '%{http_code}' -X POST "${H[@]}" -H 'Content-Type: application/octet-stream' --data-binary @file.bin "$SUPABASE_URL/storage/v1/object/phase0/test/file.bin")
res "upload 3 MB" "$([ "$code" = 200 ] && echo PASS || echo FAIL)" "http $code, $(ms $t) ms"
t=$(now); curl -s -o dl.bin "${H[@]}" "$SUPABASE_URL/storage/v1/object/authenticated/phase0/test/file.bin"
[ "$(sha256sum dl.bin | cut -d' ' -f1)" = "$SHA" ] && res "download (service key) + sha256 match" PASS "$(ms $t) ms" || { res "download + sha256 match" FAIL ""; FAILS=$((FAILS+1)); }
code=$(curl -s -o /dev/null -w '%{http_code}' "$SUPABASE_URL/storage/v1/object/public/phase0/test/file.bin")
res "anonymous public URL must NOT work (private bucket)" "$([ "$code" != 200 ] && echo PASS || echo FAIL)" "http $code"
code=$(curl -s -o /dev/null -w '%{http_code}' "$SUPABASE_URL/storage/v1/object/authenticated/phase0/test/file.bin")
res "anonymous authenticated-endpoint request must fail" "$([ "$code" != 200 ] && echo PASS || echo FAIL)" "http $code"
head -c 60000000 /dev/urandom > over.bin
code=$(curl -s -o /tmp/o.json -w '%{http_code}' -X POST "${H[@]}" -H 'Content-Type: application/octet-stream' --data-binary @over.bin "$SUPABASE_URL/storage/v1/object/phase0/test/over.bin")
res "60 MB upload (expect rejection > 50 MB limit)" "$([ "$code" != 200 ] && echo PASS-as-expected || echo UNEXPECTED-accepted)" "http $code $(head -c 100 /tmp/o.json)"

# ---- repo info for artifact/cron planning ----
if command -v gh >/dev/null && [ -n "${GH_TOKEN:-}" ]; then say ""; say "Repo private: $(gh api repos/$GITHUB_REPOSITORY --jq .private)"; fi
exit $FAILS
