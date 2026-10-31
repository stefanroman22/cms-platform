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

// --- SEC-071: GitHub MCP write tools must honour H1 (never write main in cms-platform). ---
const gh = (tool, input) => decide("", { tool: `mcp__github__${tool}`, input });

test("H1 denies github push_files to main", () => {
  assert.equal(gh("push_files", { owner: "stefanroman22", repo: "cms-platform", branch: "main", files: [] }), "deny");
});
test("H1 denies github create_or_update_file to main", () => {
  assert.equal(gh("create_or_update_file", { repo: "cms-platform", branch: "main", path: "x" }), "deny");
});
test("H1 denies github create_or_update_file with no branch (default branch is main)", () => {
  assert.equal(gh("create_or_update_file", { repo: "cms-platform", path: "x" }), "deny");
});
test("H1 denies github delete_file on main", () => {
  assert.equal(gh("delete_file", { repo: "cms-platform", branch: "main", path: "x" }), "deny");
});
test("H1 asks on github merge_pull_request in cms-platform (base not in input)", () => {
  assert.equal(gh("merge_pull_request", { repo: "cms-platform", pullNumber: 1 }), "ask");
});
test("github push_files to dev stays silent", () => {
  assert.equal(gh("push_files", { repo: "cms-platform", branch: "dev", files: [] }), null);
});
test("github write to a client repo on main stays silent", () => {
  assert.equal(gh("create_or_update_file", { repo: "client-site", branch: "main", path: "x" }), null);
});
test("github create_pull_request (base=main) is not constrained", () => {
  assert.equal(gh("create_pull_request", { repo: "cms-platform", base: "main", head: "dev" }), null);
});
