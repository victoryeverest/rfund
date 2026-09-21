# RFUND — Git Export & Push Guide

**Status: push complete.** The canonical repository now lives at
<https://github.com/victoryeverest/rfund> (branch `main`).

## Bundles (historical, superseded)

This directory previously held push-ready git bundles produced before the remote existed:

| File | Size | Contents |
|------|------|----------|
| `rfund-repo-clean-2026-09-22.bundle` | 2.8 MB | Complete source tree as a single clean commit on `main` (no venv/db/env junk). |
| `rfund-repo-2026-09-22.bundle` | 46 MB | Full history including the original scaffold commits that carried `backend/.venv` blobs. |

Clone a bundle like any remote, if you still have one:

```bash
git clone rfund-repo-clean-2026-09-22.bundle rfund
```

## Current workflow

```bash
git remote add origin https://github.com/victoryeverest/rfund.git
git push -u origin main
```

With HTTPS remotes, use a Personal Access Token as the password (GitHub:
Settings → Developer settings → Personal access tokens). With SSH, add your
key to the agent first.

## Verified at export time

- All 30 frontend routes return HTTP 200 (404 for unknown paths).
- ESLint: 0 errors, 0 warnings.
- GraphQL E2E verified through the Next.js BFF proxy.
