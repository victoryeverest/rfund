#!/bin/bash
# Build Redis + PostgreSQL servers for the RFUND sandbox runtime.
set -e
INFRA=/home/z/infra

echo "[1/4] Building Redis..."
cd "$INFRA"
rm -rf redis-7.2.5
tar xzf redis.tar.gz
cd redis-7.2.5
make -j"$(nproc)" redis-server redis-cli MALLOC=libc > "$INFRA/redis_build.log" 2>&1
test -f src/redis-server && echo "  redis-server OK"

echo "[2/4] Configuring PostgreSQL..."
cd "$INFRA/postgresql-16.4"
./configure --prefix="$INFRA/pg16" --without-readline --without-zlib > "$INFRA/pg_build.log" 2>&1
echo "  configure OK"

echo "[3/4] Compiling PostgreSQL (this takes a few minutes)..."
make -j"$(nproc)" >> "$INFRA/pg_build.log" 2>&1
make install >> "$INFRA/pg_build.log" 2>&1
test -f "$INFRA/pg16/bin/postgres" && echo "  postgres OK"

echo "[4/4] Done."
