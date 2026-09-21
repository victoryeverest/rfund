# RFUND — Git Export & Push Guide

This directory contains push-ready git artifacts for the RFUND platform.

## Bundles

| File | Size | Contents |
|------|------|----------|
| `rfund-repo-clean-2026-09-22.bundle` | 2.8 MB | **Recommended.** Complete source tree as a single clean commit on `main` (350 files: Django backend, Next.js frontend, docs, tests, scripts). No venv/db/env junk. |
| `rfund-repo-2026-09-22.bundle` | 46 MB | Full history (4 commits) including the original scaffold commits that carried `backend/.venv` blobs. Kept for provenance. |

## How to use a bundle

Clone it like any remote:

```bash
git clone rfund-repo-clean-2026-09-22.bundle rfund
cd rfund
```

Or add it to an existing repo and merge:

```bash
git remote add rfund /path/to/rfund-repo-clean-2026-09-22.bundle
git fetch rfund
git merge --allow-unrelated-histories rfund/main
```

## Pushing to a real remote (GitHub / GitLab / Bitbucket / self-hosted)

The sandbox has no remote configured and no credentials. To push, run from
`/home/z/my-project` (or your clone):

```bash
git remote add origin <YOUR_REMOTE_URL>
git push -u origin main
```

With HTTPS remotes, use a Personal Access Token as the password (GitHub:
Settings → Developer settings → Personal access tokens). With SSH, add your
key to the agent first. GitHub's 100 MB per-file limit is satisfied (largest
tracked file is ~2 MB); the clean bundle's single commit is ~2.8 MB packed.

## Verified

- `git clone` from the clean bundle checks out `main` with 350 tracked files.
- All 30 frontend routes return HTTP 200 (404 for unknown paths).
- ESLint: 0 errors, 0 warnings.
