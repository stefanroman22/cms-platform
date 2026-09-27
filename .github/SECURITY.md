# Security policy

Report a vulnerability by email to stefanromanpers@gmail.com. Do not open a public issue or push
details to a branch.

- **In scope:** anything that could compromise CMS clients: account takeover, cross-tenant data
  leaks, RCE, credential exposure, privilege escalation, persistent XSS, RLS bypass.
- **Out of scope:** best-practice nits without a concrete impact path, rate-limit fuzzing without a
  working bypass, social engineering of the operator, anything needing physical access.
- **Process:** single-operator project, no bug bounty or SLA. Acknowledgement is best-effort within
  7 days; coordinated disclosure after 90 days or once a fix is deployed, whichever is sooner.
