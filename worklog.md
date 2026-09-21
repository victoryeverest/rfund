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
- TO PUSH: need user to provide remote URL + credentials (PAT or SSH); then `git remote add origin <url> && git push -u origin main`.
