# RFUND — Implementation Plan (Phase 0)

Build order mandated by master specification §195. Each phase ends with IMPLEMENT → TEST → REVIEW → FIX → DOCUMENT → VERIFY.

| Phase | Deliverable | Verification gate |
|-------|-------------|-------------------|
| 0 | Repository audit, `ARCHITECTURE_ASSESSMENT.md`, `IMPLEMENTATION_PLAN.md`, `DOMAIN_MODEL.md` | Documents complete |
| 1 | Django project skeleton, settings graph (base/dev/prod/test), `core` app (UUID PKs, references, money utils, enums, pagination, errors, clock), Celery app, PostgreSQL + Redis runtime | `manage.py check`, `migrate` on clean PostgreSQL DB |
| 2 | `accounts` (User, roles, permissions, tokens, OTP), `customers`, `identity` (KYC), `audit` | Auth + permission unit tests, KYC state tests |
| 3 | `ledger` — double-entry engine, posting, reversal, idempotency, balance projection, snapshots | Ledger invariant tests (debits==credits, immutability, reversal net-zero, concurrency) |
| 4 | `payments` — provider abstraction, Paystack adapter, webhook pipeline, virtual accounts; `settlements` (reconciliation) | Webhook signature + duplicate-event tests, reconciliation journey test |
| 5 | `savings` — products (versioned), Digital Ajo plans, calendar schedules, contributions, payouts, goals | Schedule calendar tests (leap years, month-end, Feb), customer journey test |
| 6 | Customer web application (Next.js) — public site, auth, dashboard, savings, goals, payments, transactions | `npm run lint`, `npm run build`, browser verification |
| 7 | `agents` — territories, devices, limits, float, cash collection, settlements, commissions | Agent journey tests, limit race test |
| 8 | `loans` — products (versioned), application state machine, offers, disbursement, repayment allocation, penalties | Loan calculation + allocation + journey tests |
| 9 | `farmers` + `agriculture` — FarmerCash domain, field verification | FarmerCash journey test |
| 10 | `risk`, `fraud`, `notifications` (outbox), `support`, `reporting`, `documents`, `organizations`/`cooperatives`, `ussd` preparation | Rule engine tests, notification delivery tests |
| 11 | Full GraphQL schema wiring + security (depth, complexity, rate limits) | GraphQL tests for every query/mutation; IDOR tests |
| 12 | Seed data (`seed_demo`), sandbox bring-up, end-to-end verification | All journey tests green; browser-verified flows |
| 13 | Docker, nginx, CI/CD, env examples, Makefile | `docker compose config` validates; CI YAML valid |
| 14 | Documentation set, `IMPLEMENTATION_REPORT.md`, final QA gate | Full test suite + lint + build green |

## Concurrency & safety patterns applied throughout

1. Every financial mutation: `transaction.atomic()` + `select_for_update()` on affected ledger accounts.
2. Every external operation: unique `idempotency_key` (DB-enforced) — replays return the original result.
3. Every webhook: raw event persisted before processing; unique provider event id deduplicates.
4. Every posting: `sum(debits) == sum(credits)` enforced in service code **and** re-verified post-load in tests.
5. Balances: projection fields updated inside the posting transaction; `verify_balances()` recomputes from entries and asserts equality.
6. Reversals: new compensating transactions, never edits; link `reversal_of` both ways.
7. Notifications: outbox row committed with the financial transaction; Celery delivers asynchronously.
