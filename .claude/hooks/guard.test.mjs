// Unit tests for the PreToolUse guard (SEC-073). Run with: node --test .claude/hooks/
// Spawns guard.mjs with a hook payload on stdin and asserts the permissionDecision.
// cwd is the repo root, whose `origin` is cms-platform, so the H1 prod-repo checks fire.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const GUARD = path.join(here, "guard.mjs");
const REPO = path.resolve(here, "..", "..");

function decide(command, { tool = "Bash", input, cwd = REPO } = {}) {
  const payload = JSON.stringify({ tool_name: tool, tool_input: input ?? { command }, cwd });
  const out = execFileSync("node", [GUARD], { input: payload, encoding: "utf8" }).trim();
  return out ? JSON.parse(out).hookSpecificOutput.permissionDecision : null;
}

// --- Regression: the direct forms must still be caught exactly as before. ---
test("H1 denies a direct push to main", () => {
  assert.equal(decide("git push origin main"), "deny");
});
test("H4 denies a direct git commit --no-verify", () => {
  assert.equal(decide("git commit --no-verify -m wip"), "deny");
});
test("H2 asks on a direct apply_supabase_migration.py", () => {
  assert.equal(decide("python scripts/apply_supabase_migration.py x.sql"), "ask");
});

// --- SEC-073: the same rules must survive a one-layer wrapper. ---
test("H1 survives a bash -c wrapper", () => {
  assert.equal(decide("bash -c 'git push origin main'"), "deny");
});
test("H1 survives an sh -c wrapper", () => {
  assert.equal(decide("sh -c \"git push origin main\""), "deny");
});
test("H1 survives a bundled -lc flag", () => {
  assert.equal(decide("bash -lc 'git push origin main'"), "deny");
});
test("H1 survives an env prefix", () => {
  assert.equal(decide("env git push origin main"), "deny");
});
test("H1 survives env with an assignment", () => {
  assert.equal(decide("env GIT_PAGER=cat git push origin main"), "deny");
});
test("H1 survives a timeout wrapper (skips the DURATION positional)", () => {
  assert.equal(decide("timeout 5 git push origin main"), "deny");
});
test("H1 survives a command substitution", () => {
  assert.equal(decide("echo $(git push origin main)"), "deny");
});
test("H1 survives a backtick substitution", () => {
  assert.equal(decide("echo `git push origin main`"), "deny");
});
test("H1 survives nested wrappers", () => {
  assert.equal(decide('bash -c "env git push origin main"'), "deny");
});
test("H1 survives an eval wrapper", () => {
  assert.equal(decide("eval git push origin main"), "deny");
});
test("H4 --no-verify survives a bash -c wrapper", () => {
  assert.equal(decide("bash -c 'git commit --no-verify -m wip'"), "deny");
});
test("H2 migration survives an sh -c wrapper", () => {
  assert.equal(decide("sh -c 'python scripts/apply_supabase_migration.py drop.sql'"), "ask");
});
test("H2 migration survives a command substitution", () => {
  assert.equal(decide("echo $(python scripts/apply_supabase_migration.py drop.sql)"), "ask");
});

// --- SEC-097: an interpreter/wrapper invoked by absolute/relative path must not
//     defeat the recursive unwrap (dispatch is basename-normalised). ---
test("SEC-097 H1 survives /bin/bash -c (absolute interpreter path)", () => {
  assert.equal(decide("/bin/bash -c 'git push origin main'"), "deny");
});
test("SEC-097 H1 survives /usr/bin/env prefix (absolute wrapper path)", () => {
  assert.equal(decide("/usr/bin/env git push origin main"), "deny");
});
test("SEC-097 H1 survives ./sh -c (relative interpreter path)", () => {
  assert.equal(decide("./sh -c \"git push origin main\""), "deny");
});
test("SEC-097 H1 survives git invoked by absolute path", () => {
  assert.equal(decide("/usr/bin/git push origin main"), "deny");
});
test("SEC-097 H4 survives /usr/bin/env + -c core.hooksPath", () => {
  assert.equal(decide("/usr/bin/env git -c core.hooksPath=/dev/null commit -m x"), "deny");
});
test("SEC-097 H4 --no-verify survives /bin/bash -c wrapper", () => {
  assert.equal(decide("/bin/bash -c 'git commit --no-verify -m wip'"), "deny");
});
test("SEC-097 H2 migration survives /bin/sh -c wrapper", () => {
  assert.equal(decide("/bin/sh -c 'python scripts/apply_supabase_migration.py drop.sql'"), "ask");
});
test("SEC-097 no false positive: a non-special binary by path stays silent", () => {
  assert.equal(decide("/usr/bin/echo hello world"), null);
});

// --- SEC-098: git accepts unambiguous long-option abbreviations, so --no-verify's
//     --no-veri / --no-verif forms must also be denied (empirically git runs them). ---
test("SEC-098 H4 denies git commit --no-verif", () => {
  assert.equal(decide("git commit --no-verif -m wip"), "deny");
});
test("SEC-098 H4 denies git commit --no-veri", () => {
  assert.equal(decide("git commit --no-veri -m wip"), "deny");
});
test("SEC-098 H4 denies git push --no-veri", () => {
  assert.equal(decide("git push --no-veri origin dev"), "deny");
});
test("SEC-098 H4 --no-veri survives a bash -c wrapper", () => {
  assert.equal(decide("bash -c 'git commit --no-veri -m wip'"), "deny");
});
test("SEC-098 no false positive: --no-verbose abbreviation (--no-verb) stays silent", () => {
  assert.equal(decide("git commit --no-verb -m wip"), null);
});
test("SEC-098 no false positive: a commit message mentioning --no-verify stays silent", () => {
  assert.equal(decide('git commit -m "mention --no-verify in docs"'), null);
});

// --- No false positives: benign and quote-suppressed cases must stay silent. ---
test("single-quoted substitution is not executed → silent", () => {
  assert.equal(decide("echo 'literal $(git push origin main)'"), null);
});
test("benign wrapped command stays silent", () => {
  assert.equal(decide("bash -c 'git status'"), null);
});
test("push to dev stays silent", () => {
  assert.equal(decide("git push origin dev"), null);
});
test("a plain echo stays silent", () => {
  assert.equal(decide("echo hello world"), null);
});
