<!--
PR template — fill the sections that apply, delete the rest.
Goal: give the reviewer (or future-you reading git log) the WHY
in 60 seconds without opening the diff.
-->

## Summary

<!-- 1–2 sentences. What changed, why now. Reference issue/audit ID if relevant. -->

## Risk class

- [ ] **Trivial** (docs, comments, lockfile bump, rename) — no behavior change
- [ ] **Routine** (single-area code change, covered by tests)
- [ ] **Cross-cutting** (touches >1 area, or schema, or auth, or RLS)
- [ ] **Hot-fix** (prod broken, fast-track)

## Verification

<!-- What did you actually run? Copy the green output. -->

- [ ] Unit tests: `make test-backend` / `make test-frontend` / `make test-agent`
- [ ] Lint + typecheck: `make lint`
- [ ] Manual smoke (if UI/UX touched): describe the path
- [ ] E2E (if relevant): `cd backend && pytest auth_service/tests_integration -m integration -v`

## Deployed-state impact

- [ ] No deployed-state assertion changes
- [ ] Adds / changes a `pytest.mark.deployed_state` test (runs after promotion to `main`, post-Vercel-deploy)

## Rollback plan

<!-- One line. "Revert this commit" is fine if the change is self-contained.
For schema / RLS / auth changes, describe the reverse migration. -->

## Audit refs (if applicable)

<!-- e.g. closes BE-002, INFRA-006. Link the row in the tracker. -->
