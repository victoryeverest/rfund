# RFUND

**Rural financial services, engineered end-to-end.**

RFUND is a full-stack fintech platform for underserved and rural markets: agent-assisted
banking, savings groups, SME lending, payments, and risk management — built as a modular
Django monolith with a Next.js frontend speaking GraphQL.

![Django](https://img.shields.io/badge/backend-Django%205.1-0C4B33?logo=django&logoColor=white)
![Next.js](https://img.shields.io/badge/frontend-Next.js%2016-000?logo=next.js&logoColor=white)
![GraphQL](https://img.shields.io/badge/API-Strawberry%20GraphQL-E10098?logo=graphql&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/db-PostgreSQL%2016-336791?logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/queue-Celery%20%2B%20Redis-37814A?logo=celery&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

## What's inside

| Area | Highlights |
|------|------------|
| **Agent banking** | Field-agent onboarding, cash-in / cash-out, commissions, settlements |
| **Savings** | Group and individual plans, calendar-accurate contribution projections |
| **Loans** | SME loan origination, repayment schedules, arrears tracking |
| **Payments** | Paystack-ready rails (env-keyed), double-entry ledger core |
| **Risk & compliance** | KYC documents, fraud signals, risk scoring, full audit trail |
| **FarmerCash** | Agriculture value-chain financing for farmers and cooperatives |
| **USSD** | Feature-phone access for low-connectivity users |

## Architecture

A modular monolith: one deployable backend, 23 bounded-context Django apps, one GraphQL API.

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  Next.js 16 (port :3000)    │  GraphQL│  Django 5.1 (port :8000)     │
│  ─ public marketing site    │ ──────► │  ─ Strawberry GraphQL schema │
│  ─ /app    customer portal  │  BFF    │  ─ 23 domain apps (ledger,   │
│  ─ /agent  agent workspace  │  proxy  │    loans, savings, payments, │
│  ─ /admin  back office      │         │    agents, risk, fraud, …)   │
└─────────────────────────────┘         │  ─ Celery worker (async)     │
                                        └──────┬───────────────┬───────┘
                                               │               │
                                        PostgreSQL 16     Redis 7
                                        (port :5432)    (port :6379)
```

### Backend domain apps

`accounts` · `agents` · `agriculture` · `audit` · `cooperatives` · `core` · `customers` ·
`documents` · `farmers` · `fraud` · `identity` · `ledger` · `loans` · `notifications` ·
`organizations` · `payments` · `reporting` · `risk` · `savings` · `settlements` ·
`support` · `ussd` · plus `graphql_api` (schema, permissions, context) and `integrations`.

### Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python · Django 5.1 · Strawberry GraphQL · Celery 5.4 · Gunicorn · WhiteNoise |
| Database | PostgreSQL 16 (psycopg 3) · Redis 7 |
| Frontend | Next.js 16 · React · Apollo Client v4 · Tailwind CSS · shadcn/ui · Recharts |
| Quality | pytest (backend) · ESLint (frontend) |

## Repository layout

```
backend/            Django project (config, apps, graphql_api, integrations, tests)
src/app/            Next.js App Router (public, /app, /agent, /admin)
docs/               ARCHITECTURE_ASSESSMENT · DOMAIN_MODEL · IMPLEMENTATION_PLAN
scripts/            ensure_services.sh · start_backend.sh · api_smoke_test.py
prisma/             Frontend schema artifacts
examples/           WebSocket examples
```

## Quickstart

**Prerequisites:** Python 3.12+, Node 20+, PostgreSQL 16, Redis 7.

The all-in-one helper starts Redis and PostgreSQL, applies migrations, seeds demo data,
launches Django on `:8000` and a Celery worker:

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
scripts/ensure_services.sh
```

Then the frontend:

```bash
bun install        # or npm install
bun run dev        # http://localhost:3000
```

Manual equivalent of the backend steps:

```bash
cd backend
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver 127.0.0.1:8000
.venv/bin/celery -A config.celery_app worker --loglevel=WARNING
```

### Demo accounts (seeded)

| Role | Phone | Password |
|------|-------|----------|
| Customer | +2348012345001 … +2348012345005 | `Customer#2026` |
| Agent | +2348000000100 | `Agent#2026` |
| Admin | +2348000000000 | `Admin#2026` |

### GraphQL

The API is served at `/graphql` on the Django backend; the Next.js BFF proxies browser
requests so the frontend never talks to `:8000` directly. Example (note `frequency` is a
`String!`, not an enum):

```graphql
query {
  savingsProjection(amount: 1000, frequency: "DAILY", startDate: "2026-09-22", endDate: "2026-12-22") {
    totalContributions
    projectedAmount
  }
}
```

## Verification status

Every golden path has been verified browser → database:

- All 30 frontend routes return HTTP 200 (unknown paths correctly 404)
- ESLint: 0 errors, 0 warnings
- GraphQL E2E through the BFF proxy: `savingsProjection` returns calendar-accurate
  schedules (e.g. ₦1,000 daily over 3 months → 92 contributions, ₦92,000 total)
- Customer login → seeded savings plan visible on the dashboard
- Mobile viewport, navigation, and footer layout verified

## Documentation

- [`docs/ARCHITECTURE_ASSESSMENT.md`](docs/ARCHITECTURE_ASSESSMENT.md) — architecture review
- [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md) — domain model
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — 14-phase implementation roadmap

## License

Released under the [MIT License](LICENSE).
