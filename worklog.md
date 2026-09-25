# RFUND Worklog

---
Task ID: 1
Agent: Super Z (main)
Task: User asked "can you push to git?" — audit repo, fix hygiene, prepare push-ready artifacts; close all dangling threads surfaced along the way.

Work Log:
- Audited git state: no remote configured, no credentials, no gh CLI → external push impossible without user-provided remote.
- Found repo tracking junk: backend/.venv (9,535 files), __pycache__/.pyc (3,010), sqlite dev DBs, .env, tool-results.
- Rewrote .gitignore (Python/Django/deliverables patterns); git rm --cached all junk; tracked files 10,049 → 350.
- Committed hygiene commit 344d1c5 (proper message) + 17ca945 (ignore download bundles).
- MISHAP: `git switch --orphan` removed all tracked files from working tree; the resulting "rfund-clean" branch contained only junk (74,963 files, no source). RECOVERED via `git symbolic-ref HEAD refs/heads/main` + `git reset --mixed main` + `git restore .` — source restored byte-identical, main untouched. Lesson: orphan switch deletes tracked files; use `git commit-tree` or temp-repo for clean exports.
- Deleted bad branch, gc'd repo (pack 46 MiB = legit history incl. old venv blobs).
- Built two verified bundles in download/: full-history (46M) + clean single-commit (2.8M). Clean bundle required HEAD+main refs recorded (learned: bundle with `HEAD main` from a temp repo where the commit IS main; plain `git clone` verified working).
- Fixed frontend runtime 500s: Apollo Client v4 installed but code used v3 imports → hooks now from @apollo/client/react; onError from @apollo/client/link/error; added missing ApolloProvider (src/lib/apollo-provider.tsx wired into root layout).
- Fixed 29 pages exporting `metadata` from "use client" files (Next.js disallows) via scripts/split_client_metadata.py → server page.tsx + client page-view.tsx. All 30 routes now 200, /nonexistent properly 404.
- Fixed ESLint: 850 problems → 0. Root cause: eslint scanning backend/.venv vendored JS; added monorepo ignores. One false-positive react-hooks/set-state-in-effect documented+disabled.
- Found Django backend down + /home/z/infra wiped (PG16 + Redis builds gone). Rebuilt Redis 7.2.5 from source (OK, PONG). PostgreSQL 16.4 compiling in background.

Stage Summary:
- Repo: clean (350 source files), 2 commits added, push-ready artifacts in download/.
- Frontend: all routes green, lint clean, Apollo v4 wiring correct.
- Backend: rebuilding infra (redis done, pg in progress); next: ensure_services.sh → migrate → seed → verify GraphQL E2E.
---
Task ID: 2
Agent: Super Z (main)
Task: Rebuild wiped infrastructure, bring backend online, end-to-end browser verification, rebuild push artifacts.

Work Log:
- /home/z/infra was wiped (no PG, no Redis, no sources). Downloaded + built Redis 7.2.5 and PostgreSQL 16.4 from source into /home/z/infra (no root needed; full external network confirmed).
- MISHAP 2: shell operator precedence backgrounded the PG download before `cd` applied (tarball landed in cwd) and `&& ... &` chains killed background builds silently; partial tar extraction also broke configure. RECOVERED: dedicated build_pg.sh + nohup + foreground resumable make. Lesson: background long builds via script file, verify with ps + log growth, never trust chained `&`.
- Ran scripts/ensure_services.sh: PG cluster init, migrations applied, demo data seeded, Django on :8000, Celery worker up.
- Verified GraphQL E2E through the Next.js BFF proxy: savingsProjection(amount 1000, DAILY, 3-month window) → 92 calendar-accurate contributions, ₦92,000 total. (Note: `frequency` is String!, not enum — quote it in ad-hoc queries.)
- Agent-browser verification: homepage renders fully, zero console errors; calculator interaction live-updates (₦2,000 → ₦184,000, 92 contributions, real dates); customer login (+2348012345001 / Customer#2026) → /app/dashboard with seeded plan RF-SAV-20260921-000001 (₦500 of ₦30,500, 1/61 paid); mobile viewport collapses nav correctly; footer uses flex min-h-screen + flex-1 main pattern (sticky on short, pushed on long). Screenshots: download/rfund-homepage-verified.png, rfund-app-savings-verified.png, rfund-homepage-mobile.png.
- Rebuilt both git bundles with final tree (they predated the frontend fix commit).

Stage Summary:
- FULL STACK VERIFIED BROWSER→DB: all 30 routes 200, auth works, seeded data flows, lint clean, GraphQL correct.
- Artifacts: download/rfund-repo-clean-2026-09-22.bundle (single-commit main, plain `git clone` verified), download/rfund-repo-2026-09-22.bundle (full history), README with push instructions.
- Demo credentials: customers +2348012345001..0005 / Customer#2026; agent +2348000000100 / Agent#2026; admin +2348000000000 / Admin#2026.
- BLOCKED (needs user): actual `git push` — no remote configured, no credentials. Provide remote URL + PAT/SSH key to push.
---
Task ID: 3
Agent: Super Z (main)
Task: User provided GitHub remote + PAT — push rfund to github.com/victoryeverest/rfund as victoryeverest.

Work Log:
- Verified tool session recovered (prior 403 broken-session errors gone).
- Audited working tree: 32 files "modified" were pure mode changes 0644→0755 (0 content diffs), no untracked files.
- Set repo-local identity: victoryeverest <victoryeverest@users.noreply.github.com>.
- Committed mode normalization: 8c2e1b6 "chore: normalize file modes (0644 -> 0755)" (382 tracked files, 48M .git, largest blob 2.2MB — GitHub-safe).
- Added remote origin https://github.com/victoryeverest/rfund.git (clean URL, no embedded token).
- Pushed via one-off auth URL (token NOT persisted in .git/config): `main -> main` new branch created.
- Verified via ls-remote: remote HEAD 8c2e1b6 == local HEAD; latest commit authored by victoryeverest.
- Configured branch.main.remote/merge for future plain `git push` (needs credentials via helper on next use).
- Committed this worklog entry and pushed it.

Stage Summary:
- PUSH COMPLETE: https://github.com/victoryeverest/rfund main @ 8c2e1b6 (+ worklog commit).
- All prior dangling threads closed: repo hygiene, frontend fixes, E2E verification, artifacts, and now remote publication.
- Note: earlier history commits (8fc63b8 and below) authored as "Z User <z@container>"; only new commits carry victoryeverest identity. History rewrite possible if full re-attribution desired.
---
Task ID: 4
Agent: Super Z (main)
Task: "fix the rest" — full history re-attribution to victoryeverest, strip junk from public history, add README/LICENSE, set repo metadata.

Work Log:
- Audited: no PAT/.env/secret leaks anywhere in history; Django settings fully env-externalized (production rejects placeholder secrets).
- Added root README.md (architecture, quickstart, demo accounts, GraphQL example, verification status), MIT LICENSE, updated download/README.md (push complete). Commit e84e60f (pre-rewrite hash).
- Audited history junk: 9,698 paths (backend/.venv 9.5k, 157 __pycache__, 2 sqlite dev DBs, empty .env, .zscripts/dev.pid, 2 tool-results). No node_modules.
- Rewrote full history via filter-branch (scripts/rewrite_history.sh, deleted after use): env-filter (all 10 commits → victoryeverest <victoryeverest@users.noreply.github.com>), msg-filter (reworded 2 UUID-named commits), index-filter (stripped all junk paths), --prune-empty.
- MISHAP AVERTED: post-rewrite tree hash differed from pre-rewrite — root cause: .zscripts/dev.pid was STILL tracked in current tree; its removal was a legitimate fix (verified via tree diff = exactly that 1 file). Junk-scan "9,698 remaining" was refs/original backup ref; main history = 0 junk.
- Purged refs/original + reflogs, gc --prune=now: .git 48M → 5.0M, fsck clean, 383 files.
- Force-pushed: remote main cca3e14 → 3236a4a, ls-remote verified identical.
- GitHub API: all 10 commits attributed to victoryeverest account (author.login verified). Repo license detected as MIT, default branch main, public.
- BLOCKED (token perms): PATCH description + PUT topics both 403 — fine-grained PAT lacks Administration/Metadata write. User must set About/topics in GitHub UI or grant token permissions.

Stage Summary:
- Public repo final state: https://github.com/victoryeverest/rfund — main @ 3236a4a, 10 commits, all victoryeverest, 5MB history, zero junk, README + MIT LICENSE live.
- Remaining (user, ~30s): repo About description + topics in GitHub web UI (or re-issue PAT with admin write).
---
Task ID: 5
Agent: Super Z (main)
Task: "some things are missing on the ui, also check the backend proper, no dangling thread" — full UI completeness audit + backend verification.

Work Log:
- Infra was wiped again (PG/Redis/venv gone; node_modules survived). Rebuilt: Redis 7.2.5, PG 16.4 (make resumed across killed sessions), venv + deps. MISHAP 3: ALL background processes (nohup AND setsid) are reaped when Bash tool sessions close — EADDRINUSE revealed a stale standalone server on :3000 behind a false "old build" symptom. Lesson: long builds/verifications must run in ONE tool call, or verify the process actually owns the port.
- UI AUDIT FINDINGS: 11 of 13 Admin* GraphQL queries had NO pages; 8 mutations orphaned; ADMIN_NAV linked to 9 nonexistent routes (404s). Notifications page faked content from payments. No loan-offer decline, no goal edit, no admin customer status toggle, no OTP login UI (backend had request/verify_otp but no token issuance).
- BACKEND FIXES: login_with_otp service+resolver (TokenPair; one-time code, audit, LoginAttempt accounting); requestOtp returns {sent, devCode} with devCode STRICTLY gated on settings.DEBUG; notifications query (OutboxEvent feed scoped by payload customer_id, labels from EVENT_LABELS); AuthUser.roles added to all token responses for role-aware routing.
- FRONTEND FIXES: 9 new admin pages (loans+decide/disburse, payments+webhooks, ledger+reverse w/ entry expansion, reconciliation+run/resolve, agents+status/settlement-approve, fraud+review, support, reports+CSV render/download, audit+filters); customer status suspend/reactivate in admin customers; goal edit dialog; loan offer decline; OTP login tab (send code → devCode hint in dev → verify); real notifications feed page; role-based post-login routing (admin/agent/customer); distinct admin nav icons.
- VERIFICATION: ESLint 0/0; production build all 43 pages; 193/193 tests on PostgreSQL (new 11-test file: OTP login flows incl. one-time + purpose separation + devCode non-leak when DEBUG off; notifications scoping); 4 concurrency tests fail ONLY under SQLite (table-locked — documented as PG-required); E2E browser: 16 routes 200, admin OTP/customer logins, all 12 admin pages render live data, reconciliation run via UI created a Paystack run, reports CSV table, zero console errors; role routing verified (admin→/admin, agent→/agent).
- E2E scripts kept: scripts/e2e_verify_new_pages.sh, scripts/e2e_otp_login.py. Screenshots: download/e2e-{otp-login-dashboard,admin-reports,admin-reconciliation,admin-landing}.png.
- rg display traps documented: `rg -rn` = --replace n (mangles output); ANSI-escape eating "[m" sequences in tool output — verify suspicious "corruption" with Read before believing it.

Stage Summary:
- UI gaps closed: admin back-office complete (12/12 pages live), customer actions complete, OTP login live, notifications real, role-aware routing.
- Backend: 193/193 on PG, schema extended cleanly, no dangling orphan operations (56→75 frontend ops, all wired to pages).
- Remaining (user): repo About/topics in GitHub UI (PAT lacks admin write).
---

---
Task ID: 6
Agent: Super Z (main)
Task: Deploy RFUND to the client VPS (root@194.5.157.242) — UI on test.inyene.com, API on testapi.inyene.com, Paystack wiring, agent collections + KYC verified, demo logins for admin/agent/merchant/savers. Existing Django+React app on the VPS must not be touched.

Work Log:
- Recon: existing stack = nginx (default vhost dbug-academy), dockerized PostgreSQL/Redis/Django (dbuglabs), PM2 Next.js :3000, remote_shell :7681. test./testapi.inyene.com were falling through to the default vhost (not explicitly used) → safe to claim via explicit server_name blocks. Both domains are Cloudflare-proxied; origin :80 reachable through CF (nginx body in edge 301) → certbot HTTP-01 viable.
- SSH: password contained a leading apostrophe ('B9RtCdkEWh.4hY+) — paramiko helper scripts/vps_ssh.py (credentials via env only; debug one-offs deleted; askpass file with password deleted before any commit).
- Backend on VPS: git clone (public repo), venv (needed apt python3.12-venv — additive install), requirements installed; created rfund_app role + rfund database INSIDE the existing PG container (additive; dbuglabs data untouched); /opt/rfund/rfund.env (600) with generated secrets, ALLOWED_HOSTS/CSRF/CORS for the two domains, Redis db 1, SECURE_SSL_REDIRECT=False (nginx owns redirect; BFF→gunicorn over loopback http).
- migrate + collectstatic OK; demo logins via new scripts/vps/bootstrap_test_data.py (opt-in RFUND_BOOTSTRAP_DEMO=true; mirrors seed_demo minus fake transactions; tested locally on scratch SQLite first). Admin/KYC officer/agent/3 customers in 3 KYC states + unfunded plans.
- Frontend on VPS: bun 1.4.2 installed, bun install --frozen-lockfile (837 pkgs), NODE_OPTIONS=--max-old-space-size=2304 bun run build — OK on 1 vCPU/3.8GB.
- systemd: rfund-backend (gunicorn 127.0.0.1:8010), rfund-celery (worker), rfund-celery-beat (added later), rfund-frontend (node standalone 127.0.0.1:3010, RFUND_BACKEND_URL=http://127.0.0.1:8010). All enabled + active.
- nginx sites-available/rfund: 80-block (ACME webroot + redirect) + two 443-blocks (per-hostname upstreams, /media/ alias, 25M body). certbot certonly --webroot → LE cert for both domains (renewal deploy-hook reloads nginx). External: https://test.inyene.com 200 RFUND title; https://testapi.inyene.com/health/ready ok (db+redis ok); GraphQL + BFF both responding.
- BUG FOUND & FIXED #1 (live E2E): frontend called submitKYC/reviewKYC but schema fields are submitKyc/reviewKyc — customer KYC submission and admin review never actually worked. Fixed operations.ts; added scripts/vps/validate_operations.py (validates all 62 gql documents against the real schema — now a deploy checklist item); rebuilt + redeployed.
- BUG FOUND & FIXED #2 (UI walkthrough): agent collections UI never sent a plan target → money ledgered + receipted but plans never credited. Fixed both ways: backend auto-applies to the customer's sole ACTIVE plan (ambiguity-safe: no attribution with 0/2+ active plans); new agentCustomerPlans query + Savings-plan selector (Auto default) on agent Collections and Customer detail pages. 2 new tests (auto-apply + ambiguity guard). UI-verified end-to-end: collection ₦1000 via UI → customer plan 4500→5500, 9/61→11/61 paid.
- BUG FOUND & FIXED #3 (deployed ops): apps/core/beat.py was dead config (never imported) — dispatch-outbox/schedules/reconciliation/reminders NEVER ran anywhere (17 undelivered outbox events on the VPS proved it). Refactored to pure BEAT_SCHEDULE dict applied in config/celery_app.py; run_reconciliation task now defaults to settings.PAYMENT_PROVIDER (was hardcoded 'local'); tests/test_beat.py pins the wiring (3 tests). Added rfund-celery-beat systemd unit (flag fix: --schedule not --schedule-file). After deploy: dispatch_outbox succeeded → 17/17 events delivered, sms_sent logs flowing.
- KYC verified through the actual admin UI (Ibrahim approved with reason → queue empty → API kycStatus VERIFIED/STANDARD).
- Paystack: adapter fully wired server-side; webhook live at https://testapi.inyene.com/payments/webhooks/paystack; keys are account-specific → /opt/rfund/PAYSTACK_SETUP.md on the VPS documents the 3-step activation (paste sk_test keys in rfund.env, restart, register webhook URL). Until then card payments fail with a clear "not configured" error; agent cash path funds plans.
- E2E scripts/vps/e2e_vps_workflows.py (rerunnable, state-aware): final run 7/7 PASS — all role logins, collection→plan credit (5500→7000), KYC verified, admin dashboard live (₦8000 collections today).
- Existing app integrity verified post-deploy: learn.dbughouse.com 200, dbuglabs Django responding, dbuglabs-db connections healthy, shell.dbughouse.com same-as-before (its ttyd 404 is pre-existing backend behavior, identical direct vs CF).
- Browser verification (agent-browser): customer/agent/admin logins through the real UI, screenshots in download/vps-*.png.
- docs/DEPLOYMENT.md added to the repo (referenced by settings comments since inception; now real): topology, env template, unit patterns, step-by-step initial deployment, ops notes.

Stage Summary:
- LIVE: https://test.inyene.com (RFUND UI) + https://testapi.inyene.com (GraphQL API, health green) behind Cloudflare with LE certs; 4 systemd services active; existing co-hosted apps untouched.
- Demo logins: admin +2348000000000/Admin#2026 · KYC officer +2348000000002/Kyc#2026 · agent/merchant +2348000000100/Agent#2026 · savers +2348012345001-5003/Customer#2026.
- Three real bugs fixed along the way (KYC mutation casing, agent collection plan targeting, dead celery beat) — each with tests, each deployed + verified live.
- Remaining (user, ~5 min): paste Paystack TEST keys into /opt/rfund/rfund.env per /opt/rfund/PAYSTACK_SETUP.md and register the webhook URL in the Paystack dashboard.
