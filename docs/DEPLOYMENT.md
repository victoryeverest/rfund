# RFUND Deployment Runbook

This documents the reference deployment used for the test environment at
`test.inyene.com` (UI) and `testapi.inyene.com` (API), on a single Ubuntu
24.04 VPS (1 vCPU / 4 GB) that also hosts other applications. The RFUND
stack is fully isolated: its own directory, ports, database role, Redis DB
index and systemd units — nothing is shared with co-hosted apps except the
PostgreSQL and Redis containers themselves.

## Topology

```
Cloudflare (DNS + TLS edge)
  ├── test.inyene.com    ──► nginx :443 ──► Next.js standalone  127.0.0.1:3010
  └── testapi.inyene.com ──► nginx :443 ──► gunicorn (Django)   127.0.0.1:8010
                                             ├── PostgreSQL (container, db: rfund)
                                             ├── Redis (container, db 1)
                                             ├── Celery worker
                                             └── Celery beat (periodic schedule)
```

The Next.js server is a BFF: the browser only talks to `test.inyene.com`;
server-side routes proxy GraphQL to the backend over loopback
(`RFUND_BACKEND_URL=http://127.0.0.1:8010`). Paystack webhooks arrive at
`https://testapi.inyene.com/payments/webhooks/paystack` and are verified by
HMAC-SHA512 signature.

## On-disk layout

| Path | Purpose |
|------|---------|
| `/opt/rfund/repo` | git clone of this repository |
| `/opt/rfund/venv` | Python 3.12 virtualenv |
| `/opt/rfund/rfund.env` | production env file (chmod 600, loaded by systemd) |
| `/opt/rfund/media`, `/opt/rfund/staticfiles` | uploads / collected static |
| `/opt/rfund/logs` | gunicorn access/error logs, celerybeat schedule |
| `/opt/rfund/PAYSTACK_SETUP.md` | how to drop in Paystack keys |

## systemd units

`rfund-backend` (gunicorn :8010, 3 workers), `rfund-celery` (worker,
concurrency 2), `rfund-celery-beat` (periodic scheduler — **required**, the
notification outbox, schedule refresh, reconciliation and reminders are all
beat-driven), `rfund-frontend` (Next.js standalone :3010). All load
`/opt/rfund/rfund.env` via `EnvironmentFile=`.

## Environment file ( essentials )

```
DJANGO_ENV=production
DJANGO_SECRET_KEY=<50+ random chars>
ALLOWED_HOSTS=testapi.inyene.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://test.inyene.com,https://testapi.inyene.com
CORS_ALLOWED_ORIGINS=https://test.inyene.com
DATABASE_URL=postgresql://rfund_app:<pw>@127.0.0.1:5432/rfund
REDIS_URL=redis://127.0.0.1:6379/1        # db index 1 keeps Celery isolated
PAYMENT_PROVIDER=paystack
PAYSTACK_SECRET_KEY=                      # see /opt/rfund/PAYSTACK_SETUP.md
SECURE_SSL_REDIRECT=False                 # nginx owns the 80->443 redirect;
                                          # the BFF reaches gunicorn over http
MEDIA_ROOT=/opt/rfund/media
STATIC_ROOT=/opt/rfund/staticfiles
```

## Initial deployment steps

1. `mkdir -p /opt/rfund && git clone https://github.com/victoryeverest/rfund.git /opt/rfund/repo`
2. `python3 -m venv /opt/rfund/venv && /opt/rfund/venv/bin/pip install -r /opt/rfund/repo/backend/requirements.txt`
3. Create the database (inside the existing PostgreSQL container — additive,
   does not touch other databases):
   `docker exec <pg> psql -U <super> -c "CREATE ROLE rfund_app LOGIN PASSWORD '...';"`
   `docker exec <pg> psql -U <super> -c "CREATE DATABASE rfund OWNER rfund_app;"`
4. Write `/opt/rfund/rfund.env` (template above), `chmod 600`.
5. `cd /opt/rfund/repo/backend && set -a && source /opt/rfund/rfund.env && set +a`
   then `../../venv/bin/python manage.py migrate --noinput && ... collectstatic --noinput`
6. Create demo logins (test deployments only — explicit opt-in):
   `RFUND_BOOTSTRAP_DEMO=true ../../venv/bin/python manage.py shell < ../../scripts/vps/bootstrap_test_data.py`
7. Frontend: `curl -fsSL https://bun.sh/install | bash`, then in `/opt/rfund/repo`:
   `bun install --frozen-lockfile && NODE_OPTIONS=--max-old-space-size=2304 bun run build`
8. Install the four systemd units (see `/etc/systemd/system/rfund-*.service`
   patterns) and `systemctl enable --now` them.
9. nginx: `sites-available/rfund` with one 80-block (ACME webroot + redirect)
   and two 443-blocks (per-hostname upstreams, `/media/` alias, 25 MB body
   limit for KYC uploads). Obtain certificates:
   `certbot certonly --webroot -w /var/www/html -d test.inyene.com -d testapi.inyene.com`
10. Validate the frontend operations against the schema:
    `cd backend && DATABASE_URL=sqlite:///tmp/v.sqlite3 DJANGO_ENV=test ../../venv/bin/python ../scripts/vps/validate_operations.py`
11. Verify the live workflows:
    `python3 scripts/vps/e2e_vps_workflows.py https://test.inyene.com`

## Demo logins (test deployments)

| Role | Phone | Password |
|------|-------|----------|
| Super admin | +2348000000000 | Admin#2026 |
| KYC officer | +2348000000002 | Kyc#2026 |
| Agent (merchant) | +2348000000100 | Agent#2026 |
| Savers | +2348012345001 … 5003 | Customer#2026 |

The savers cover three KYC states (VERIFIED / PENDING / NOT_STARTED) so the
full KYC review workflow can be demonstrated.

## Operational notes

- **Agent collections**: collections without an explicit plan target are
  auto-applied to the customer's sole ACTIVE savings plan; when several
  plans are active the agent UI forces an explicit choice.
- **Notifications**: `SMS_PROVIDER=console` logs messages to the Celery
  journal — switch to a real gateway by setting `SMS_PROVIDER` +
  `SMS_PROVIDER_KEY` and restarting.
- **Reconciliation**: the beat task defaults to the configured
  `PAYMENT_PROVIDER`; runs every 30 minutes.
- **Renewals**: certbot's systemd timer renews certificates; the deploy hook
  `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh` reloads nginx.
- **Updates**: `cd /opt/rfund/repo && git pull`, re-run migrations if any,
  rebuild the frontend if `src/` changed, then
  `systemctl restart rfund-backend rfund-celery rfund-frontend`.
