# ADR-0007: Production changes only through the manual "Promote dev → main" action

Status: Accepted
Date: 2026-09-27

## Context

The earlier pipeline ran CI on every push, auto-merged `dev` into production and ran smoke tests
with auto-rollback. For a one-operator project it was slow and flaky (E2E data pollution blocked
releases), and it cost Action minutes on every push. The operator wants to decide when production
changes.

## Decision

- Feature branches and `dev` run no GitHub Actions. Pushing to `dev` makes Vercel build preview
  deployments of both apps (on the shared production database, see ADR-0001).
- Production is the `main` branch. It changes only when someone runs the manual
  "Promote dev → main" workflow (`.github/workflows/promote.yml`). The workflow:
  1. runs gitleaks on the working tree;
  2. runs frontend `npm ci`, lint and build;
  3. runs backend `pip install --require-hashes -r requirements.lock`, ruff and `compileall`;
  4. fast-forwards `main` to `dev` with `PROMOTE_TOKEN`;
  5. calls the frontend and backend Vercel production deploy hooks.
- Tests are not part of the gate. They are run locally with `make ci`. The pre-commit hook runs
  lint and gitleaks on every commit.
- Rollback is manual, in Vercel. CodeQL runs weekly only.

## Consequences

- Releases are deliberate, fast (about 5–7 minutes) and cheap.
- **Nothing forces tests to run before production.** A broken test suite can be promoted.
- "Only the promote action writes to `main`" is a convention backed by a local Claude Code hook
  (`.claude/hooks/guard.mjs`), not by GitHub branch protection. The owner's credentials could
  still push to `main`.
- There is no automatic rollback; a bad deploy stays live until someone reverts it in Vercel.
- Do NOT: push to `main`, deploy production from the CLI, re-add push-triggered CI or auto-merge to
  `main`, or skip the pre-commit hook. Reintroducing CI or protected-branch PR flows needs a new
  ADR.
