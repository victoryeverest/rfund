# RFUND — Architecture Assessment (Phase 0)

**Date:** 2026-09-21
**Scope:** Audit of the supplied RFUND prototype (`rfund.zip`) and the target monorepo before implementation.

---

## 1. Current Architecture Assessment

### 1.1 What was supplied

The supplied prototype is a **static, single-page marketing site** with zero backend:

| File | Role |
|------|------|
| `index.html` | Single page: hero, product cards, savings calculator, loan interest form, payment modal, join form |
| `styles.css` | Hand-written CSS design system (~500 lines), green/gold palette |
| `app.js` | Client-side calculator + `localStorage` persistence |
| `assets/rfund-hero.png` | Hero photograph |

### 1.2 Existing features

1. **Public marketing content** — Digital Ajo / Rural Loans / FarmerCash positioning, trust strip (Daily thrift, USSD, Agents), footer with agent USSD code `*777*RFUND#`.
2. **Savings calculator** — amount × frequency (daily/weekly/monthly) × tenure (quarterly/bi-yearly/yearly) → estimated payout.
3. **Loan interest form** — product, name, phone, amount, purpose; saved to `localStorage`.
4. **Join form** — name, phone, interest; saved to `localStorage`.
5. **Payment method modal** — four method buttons that only set status text.

### 1.3 Existing reusable assets

| Asset | Reuse decision |
|-------|----------------|
| Color palette (`--green-900 #123328`, `--green-700 #21634d`, `--green-500 #2f8a63`, `--gold #e7b451`, `--tomato #d8583b`, `--ink #17211d`) | **Retained** — becomes the RFUND design tokens |
| Inter typeface, 800-weight headings, `--gold` eyebrow labels | **Retained** — typography direction |
| Product framing: Digital Ajo, Rural Loans, FarmerCash, agent network, USSD access | **Retained** — information architecture and terminology |
| Savings planner concept (amount / frequency / tenure) | **Retained** — reimplemented as a **server-authoritative** calculator + real plan creation |
| 48px minimum touch targets, responsive single-column mobile layout, `aria-live` status regions, `role="status"` | **Retained** — accessibility baseline extended to WCAG 2.1 AA |
| Hero photograph | **Retained** — reused as the public-site hero |

### 1.4 Identified inconsistencies / violations of the master specification

| # | Prototype behaviour | Specification requirement | Resolution |
|---|---------------------|---------------------------|------------|
| 1 | Savings estimate uses fixed day multipliers (`quarterly = 91`, `monthly = 1/30.4167`) | §18: generate **actual calendar dates**, never fixed day multipliers | Backend schedule engine generates real dates (`relativedelta`), handles month-end clamping, leap years |
| 2 | Loan application saved to `localStorage` | §52: `applyForLoan` GraphQL mutation, server-side state machine | Full loan application domain implemented server-side |
| 3 | Payment buttons claim readiness but do nothing | §104: no placeholder buttons | Payments implemented through the `PaymentProvider` abstraction; every button performs a real action |
| 4 | No authentication | §60: phone/password/OTP, sessions, RBAC | Full token auth with refresh + rotation, OTP architecture, granular RBAC |
| 5 | No database, no ledger | §14: double-entry ledger is the core | PostgreSQL + immutable double-entry ledger engine |
| 6 | Client is the source of financial truth (calculator) | §21: backend is authoritative | All financial figures in the authenticated app come from GraphQL |
| 7 | "Live deployment can connect …" copy implies future integration | §102: no fake integrations | Paystack integration implemented for real (signature-verified webhooks, server-side verification); sandbox runs use an explicit, clearly-labelled local provider |
| 8 | Single page only | §65: public site + `/app` + `/agent` + `/admin` areas | Full route map implemented |

### 1.5 What is missing entirely

Authentication, authorization, customers, KYC, financial accounts, ledger, payments, webhooks, reconciliation, savings engine, goals, loans, repayment, FarmerCash domain, agents, float, settlements, commissions, cooperatives, risk, fraud, notifications, support, reporting, audit, documents, USSD preparation, tests, Docker, CI/CD, documentation.

**Conclusion:** the prototype is a **design reference only**. Nothing from its JavaScript can be reused as business logic. Its CSS/tokens and product framing are carried forward into the Next.js design system.

---

## 2. Proposed Final Architecture

```
                    ┌────────────────────────────────────────────┐
                    │  Next.js 16 web app (repo root, port 3000) │
                    │  public site · /app · /agent · /admin      │
                    │  Apollo Client → /api/graphql (BFF proxy)  │
                    └───────────────────┬────────────────────────┘
                                        │  HTTP (relative paths)
                            ┌───────────▼───────────┐
                            │  Django 5.1 modular   │
                            │  monolith + Strawberry│
                            │  GraphQL (port 8000)  │
                            └───────────┬───────────┘
        ┌───────────────┬───────────────┼────────────────┬───────────────┐
        │               │               │                │               │
   accounts/       ledger/         savings/          loans/         payments/
   identity/       (double-        agents/           farmers/       integrations/
   customers/       entry core)    cooperatives/     agriculture/   (Paystack)
   audit/          settlements/    notifications/    risk/ fraud/
   support/        reporting/      documents/        ussd/ (prep)
        │               │               │                │               │
        └───────────────┴───────┬───────┴────────────────┴───────────────┘
                                │
                    ┌───────────▼───────────┐
                    │ PostgreSQL 16 (SQL)   │
                    │ Redis 7 (broker/cache)│
                    │ Celery worker + beat  │
                    └───────────────────────┘
```

Key decisions (aligned to the specification):

1. **Modular monolith** (§125) — one Django process, many bounded apps, domain logic in application services, never in resolvers (§7).
2. **Strawberry GraphQL** is the only application API (§5). A thin Django REST view exists **only** for the Paystack webhook (§25 requires a dedicated HTTP webhook endpoint — GraphQL is not a webhook transport).
3. **Ledger-first accounting** (§3.2) — balances derive from immutable double-entry postings; a transactionally-consistent balance projection is maintained on each `FinancialAccount` and is verifiable via `LedgerService.verify_balances()`.
4. **Provider abstraction** (§22, §150) — `PaymentProvider`, `IdentityVerificationProvider`, `NotificationProvider`, `SMSProvider`, `StorageProvider` interfaces with swappable adapters (Paystack initial; local adapter for development).
5. **Outbox pattern** (§107) — domain events are persisted in the same transaction as financial postings, then dispatched to Celery for notification delivery.
6. **Opaque, revocable auth tokens** (hashed at rest, rotation, refresh, device binding) rather than JWT — better fit for session revocation and audit requirements (§60).

### 2.1 Sandbox vs production topology

| Concern | Production (canonical, Docker) | This sandbox (verification) |
|---------|-------------------------------|------------------------------|
| Database | `postgres:16` container, `DATABASE_URL` | PostgreSQL 16.4 compiled from source at `/home/z/infra/pg16`, same `DATABASE_URL` mechanics |
| Redis | `redis:7` container | Redis 7.2.5 compiled from source at `/home/z/infra/redis-7.2.5` |
| Backend | gunicorn behind nginx | `runserver 127.0.0.1:8000` (loopback only) |
| Web | Next.js standalone behind nginx | Next.js dev server, port 3000 (the only exposed port) |
| Web→API | nginx routes `/api/` to Django | Next.js route handlers proxy `/api/graphql` to `127.0.0.1:8000` (relative paths preserved) |
| Paystack | Real keys, signature-verified webhooks | `local` provider — deterministic, clearly non-production; Paystack adapter fully implemented and unit-tested against recorded payload shapes |

Both topologies run the **same** Django settings module graph; only environment variables differ.

---

## 3. Proposed Database / Domain Model

Full column-level detail lives in `docs/DOMAIN_MODEL.md` and the live migrations. Summary of aggregates:

- **Identity & access:** `User` (phone/email + password), `Role`, `Permission`, `UserRole`, `AuthToken`, `OTPCode`, `LoginAttempt`
- **Party:** `Customer`, `Agent`, `StaffProfile`, `Organization`, `Cooperative`, `CooperativeMember`
- **KYC:** `KYCProfile`, `IdentityDocument`, `KYCVerification`, `KYCReview`
- **Ledger:** `LedgerAccount`, `LedgerTransaction`, `LedgerEntry`, `AccountingPeriod`, `BalanceSnapshot`, `LedgerBatch`
- **Payments:** `Payment`, `PaymentAttempt`, `PaymentWebhookEvent`, `PaymentProviderEvent`, `VirtualAccount`
- **Savings:** `SavingsProduct(+Version)`, `SavingsAccount`, `SavingsPlan`, `SavingsScheduleItem`, `SavingsContribution`, `SavingsPayout`, `SavingsGoal`
- **Loans:** `LoanProduct(+Version)`, `LoanApplication`, `LoanAssessment`, `LoanOffer`, `Loan`, `RepaymentScheduleItem`, `Repayment`, `Penalty`
- **FarmerCash:** `FarmerProfile`, `Farm`, `FarmSeason`, `Crop`, `FarmActivity`, `InputRequirement`, `InputSupplier`, `FieldVerification`
- **Agents:** `AgentTerritory`, `AgentDevice`, `AgentLimit`, `AgentTransaction`, `AgentFloatMovement`, `AgentSettlement`, `CommissionRule`, `CommissionTransaction`
- **Risk/Fraud:** `RiskRule`, `RiskAssessment`, `RiskFactor`, `FraudRule`, `FraudAlert`, `FraudCase`
- **Ops:** `NotificationTemplate`, `NotificationEvent`, `NotificationDelivery`, `OutboxEvent`, `AuditEvent`, `SupportTicket`, `SupportMessage`, `ReconciliationRun/Item/Exception`, `USSDSession` (prepared)

---

## 4. GraphQL Architecture

Single schema assembled from domain modules (relay-style connections where lists are large; cursor pagination everywhere):

- **Public/auth mutations:** `registerCustomer`, `requestOtp`, `verifyOtp`, `login`, `refreshToken`, `logout`, `updateProfile`, `submitKYC`
- **Savings:** `createSavingsPlan`, `cancelSavingsPlan`, `makeSavingsContribution`, `requestSavingsPayout`, `createSavingsGoal`, `updateSavingsGoal`, `deleteSavingsGoal`, `contributeToGoal`
- **Loans:** `applyForLoan`, `acceptLoanOffer`, `rejectLoanOffer`, `makeRepayment`
- **Agent:** `agentCashCollection`, `agentCustomerPayout`, `requestAgentSettlement`
- **Support:** `createSupportTicket`, `replySupportTicket`
- **Admin:** `reviewKyc`, `approveLoanApplication`, `rejectLoanApplication`, `disburseLoan`, `reverseLedgerTransaction`, `approveAgentSettlement`, `resolveReconciliationException`, `flagFraudAlert`, … (all permission-checked, all audited)

Security: depth limiting, complexity guard, operation-size cap, per-role mutation rate limits, structured error codes (`INSUFFICIENT_FUNDS`, `KYC_REQUIRED`, …), no stack traces, no IDOR (object-level checks in every resolver), admin schema fields gated by permission (§116).

---

## 5. Security Architecture

Phone/email + password auth (Argon2 via Django's password hashing stack), opaque tokens hashed at rest, refresh-token rotation with reuse detection, OTP codes hashed + rate-limited + attempt-capped, login throttling, RBAC with 15 roles / 40+ granular permissions, object-level authorization everywhere, webhook HMAC verification, private document storage (no public URLs), audit trail for privileged operations, structured logging with `request_id`, secrets only via environment, production boot validation (rejects `DEBUG=True`, missing vars), CSP/HSTS/X-Frame headers via security middleware.

## 6. Payment Architecture

`PaymentProvider` interface → `PaystackProvider` (initialize / verify / transfer / verify-transfer / get transaction, HMAC-SHA512 webhook signature verification) → normalized `PaymentProviderError` → RFUND domain errors. Dedicated Django webhook view stores raw events first, processes idempotently (unique provider event id), posts to ledger, emits outbox events. Reconciliation compares provider transactions to ledger postings. Virtual-account model prepared (`VirtualAccount`) without Paystack-specific concepts in the customer model.

## 7. Implementation Phases

See `IMPLEMENTATION_PLAN.md`. Order follows §195: infrastructure → identity → ledger → payments → savings → web app → agents → loans → FarmerCash → risk/fraud/reporting, with tests and documentation at every phase.

## 8. Risks and Ambiguities

| Risk / ambiguity | Safe handling |
|------------------|---------------|
| RFUND's regulatory status (licensing) unknown | §2 honored: no claims of being a bank; configurable provider abstractions; `docs/REGULATORY_ASSUMPTIONS.md` marks every item requiring legal confirmation |
| Interest method / rates not specified | Configurable per `LoanProduct` (flat and declining-balance implemented); no hard-coded rates anywhere |
| Ajo payout policy (who receives the pot) | Payout policy field on product + explicit `PayoutPolicy` enum; payouts require eligibility validation and are ledger-posted |
| Paystack sandbox unreachable from sandbox | Local provider adapter for the sandbox run only — explicitly labelled, guarded by `ALLOW_LOCAL_PAYMENT_PROVIDER` which is refused when `DJANGO_ENV=production` |
| Concurrent money movement | `select_for_update` on account rows + unique idempotency keys + DB constraints; concurrency tests included |

## 9. Exact files created / modified

Created: `backend/**` (24 Django apps + config + integrations + tests), Next.js app at repo root (`src/**` rewritten), `docs/**` (20+ files), `infrastructure/**` (nginx conf, Dockerfiles), `docker-compose.yml`, `.env.example`, `.env.test.example`, `Makefile`, `.github/workflows/ci.yml`, `scripts/**` (sandbox runtime).

Modified: `package.json` (scripts, Apollo deps), `Caddyfile` (unchanged — gateway already routes to :3000), `.gitignore` (backend venv, caches, media).

Nothing from the prototype was destroyed: its source is preserved verbatim under `docs/prototype/` and its tokens/assets are carried into the new design system.
