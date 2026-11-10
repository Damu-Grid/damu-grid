# GitHub rules

Intended remote: `https://github.com/Damu-Grid/<repo>` (exact repo name to confirm when the organisation repo is created). **Do not push, create issues on GitHub, or change repository settings from an agent unless a human has approved that specific action.** This folder is local starting content.

## Branching

- `main` is protected once GitHub is connected. No direct commits to `main` after the initial bootstrap, if protection is available.
- Branch names: `feat/<issue-id>-short-slug`, `fix/<issue-id>-short-slug`, `docs/<slug>`.
- Short-lived branches. Rebase or merge from `main` before asking for review.

## Commits

Incremental commits are **proof that the work was done in the window**. One large commit at the end will be checked closely (official brief).

Use Conventional Commits:

- `feat(backend): accept reserves a unit`
- `fix(pipeline): treat missing exposure as ineligible`
- `docs(eval): record July origin counts`
- `test(api): reject duplicate reservation`
- `chore: add ruff config`

Do not backdate author or committer dates. Do not force-push `main`. Force-push to a personal feature branch only if the teammate agrees and the branch is not shared.

## Pull requests

Use `.github/pull_request_template.md`. Keep PRs small enough to review in minutes. Reference the issue id from `issues/ISSUES.md`. Anyone can review; prefer a look from the area owner in CODEOWNERS when they are online. Do not block a production-stopping fix.

Suggested labels (create when the repo exists): `tier-1`, `tier-2`, `backend`, `frontend`, `pipeline`, `forecasting`, `simulation`, `docs`, `demo`, `blocked`, `good-first-task`.

## Checkpoints (merge discipline)

- **Tue 20:00 EAT:** Check-in 1. Merge what already runs. Do not leave half-broken `main`.
- **Wed 06:00 EAT:** Check-in 2. Same rule.
- **Wed 09:30 EAT:** Merge freeze for demo recording, except critical fixes.
- **Wed 11:15 EAT:** Merge freeze for submission, except documentation or access fixes.

## Secrets and data

- Never commit `.env`, API keys, or demo passwords. `.env.example` has names only.
- Never rewrite `data/raw/`.
- `data/processed/` is gitignored. Document regeneration commands instead of committing large SQLite files, unless a tiny fixture is needed for tests (place fixtures under `tests/fixtures/`).

## Releases and visibility

The repository must be **public by the submission deadline**. Make it public with enough time to fix link permissions on the video and slides. The official brief required the GitHub link on the check-in form by Tue 14:00 EAT; if that already slipped, submit as soon as the empty or skeleton repo exists.
