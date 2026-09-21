#!/bin/bash
# Idempotent service supervisor for the RFUND sandbox.
# Ensures: redis, postgresql, django backend (and celery worker) are running.
# Safe to call repeatedly. Each step checks current state first.

set -u
INFRA=/home/z/infra
BACKEND=/home/z/my-project/backend
REDIS_CLI="$INFRA/redis-7.2.5/src/redis-cli"
REDIS_SERVER="$INFRA/redis-7.2.5/src/redis-server"
PG_BIN="$INFRA/pg16/bin"
PGDATA="$INFRA/pgdata"
PG_LOG="$INFRA/postgres.log"

echo "== RFUND service supervisor =="

# --- 1. Redis ---------------------------------------------------------------
if "$REDIS_CLI" ping 2>/dev/null | grep -q PONG; then
    echo "[redis] already running"
else
    mkdir -p "$INFRA/redis-data"
    nohup "$REDIS_SERVER" --port 6379 --daemonize no --dir "$INFRA/redis-data" \
        --save "" --appendonly no --protected-mode yes --bind 127.0.0.1 \
        > "$INFRA/redis.log" 2>&1 < /dev/null &
    sleep 1
    if "$REDIS_CLI" ping 2>/dev/null | grep -q PONG; then
        echo "[redis] started"
    else
        echo "[redis] FAILED to start"; exit 1
    fi
fi

# --- 2. PostgreSQL ------------------------------------------------------------
if "$PG_BIN/pg_isready" -h 127.0.0.1 -p 5432 > /dev/null 2>&1; then
    echo "[postgres] already running"
else
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
        echo "[postgres] initializing cluster..."
        "$PG_BIN/initdb" -D "$PGDATA" -U rfund --auth=trust -E UTF8 > "$INFRA/initdb.log" 2>&1
        "$PG_BIN/pg_ctl" -D "$PGDATA" -o "-p 5432 -k /tmp -c listen_addresses=127.0.0.1" -l "$PG_LOG" start > /dev/null 2>&1
        sleep 2
        "$PG_BIN/createdb" -h 127.0.0.1 -U rfund rfund 2>/dev/null || true
        "$PG_BIN/psql" -h 127.0.0.1 -U rfund -d rfund -c "ALTER USER rfund PASSWORD 'rfund';" > /dev/null 2>&1
        echo "[postgres] cluster created"
    else
        "$PG_BIN/pg_ctl" -D "$PGDATA" -o "-p 5432 -k /tmp -c listen_addresses=127.0.0.1" -l "$PG_LOG" start > /dev/null 2>&1
        sleep 2
    fi
    if "$PG_BIN/pg_isready" -h 127.0.0.1 -p 5432 > /dev/null 2>&1; then
        echo "[postgres] running"
    else
        echo "[postgres] FAILED to start"; tail -5 "$PG_LOG"; exit 1
    fi
fi

# --- 3. Django backend ----------------------------------------------------------
export DJANGO_SETTINGS_MODULE=config.settings
export DJANGO_ENV=development
export DATABASE_URL="${RFUND_DATABASE_URL:-postgres://rfund:rfund@127.0.0.1:5432/rfund}"
export REDIS_URL="${RFUND_REDIS_URL:-redis://127.0.0.1:6379/0}"
export CELERY_BROKER_URL="$REDIS_URL"
export CELERY_RESULT_BACKEND="$REDIS_URL"
export ALLOW_LOCAL_PAYMENT_PROVIDER="${RFUND_ALLOW_LOCAL_PROVIDER:-true}"
export PAYMENT_PROVIDER="${RFUND_PAYMENT_PROVIDER:-local}"
export SMS_PROVIDER=console
export DJANGO_SECRET_KEY="${RFUND_DJANGO_SECRET_KEY:-sandbox-dev-only-key-change-me}"
export LOG_LEVEL=INFO
cd "$BACKEND"

if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health/live 2>/dev/null | grep -q 200; then
    echo "[django] already running"
else
    # Migrate + seed (idempotent) before starting
    .venv/bin/python manage.py migrate --noinput > /tmp/rfund_migrate.log 2>&1 \
        && echo "[django] migrations applied" || { echo "[django] migrate FAILED"; tail -5 /tmp/rfund_migrate.log; exit 1; }
    if [ "${RFUND_SKIP_SEED:-0}" != "1" ]; then
        .venv/bin/python manage.py seed_demo > /tmp/rfund_seed.log 2>&1 \
            && echo "[django] demo data seeded" || { echo "[django] seed FAILED (continuing)"; tail -3 /tmp/rfund_seed.log; }
    fi
    nohup .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload \
        > /tmp/rfund_django.log 2>&1 < /dev/null &
    sleep 3
    if curl -s http://127.0.0.1:8000/health/live 2>/dev/null | grep -q ok; then
        echo "[django] running on 127.0.0.1:8000"
    else
        echo "[django] FAILED to start"; tail -10 /tmp/rfund_django.log; exit 1
    fi
fi

# --- 4. Celery worker --------------------------------------------------------
if [ "${RFUND_START_CELERY:-1}" = "1" ]; then
    if pgrep -f "celery.*worker" > /dev/null 2>&1; then
        echo "[celery] already running"
    else
        nohup .venv/bin/celery -A config.celery_app worker --loglevel=WARNING --concurrency=1 \
            > /tmp/rfund_celery.log 2>&1 < /dev/null &
        echo "[celery] worker started"
    fi
fi

echo "== all services ready =="
