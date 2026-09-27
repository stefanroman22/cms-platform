#!/usr/bin/env node
// PreToolUse guardrails for the CMS repo. Reads the hook payload on stdin and
// answers with a permissionDecision ("deny" or "ask"), or stays silent to let
// the normal permission flow decide. Fails open: an internal error never
// blocks a tool call.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const PROD_REPO = /cms-platform(\.git)?\/?$/i;

function decide(permissionDecision, reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision,
        permissionDecisionReason: reason,
      },
    }),
  );
  process.exit(0);
}

function git(dir, args) {
  try {
    return execFileSync("git", ["-C", dir, ...args], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 5000,
    }).trim();
  } catch {
    return "";
  }
}

const isProdRepo = (dir) => PROD_REPO.test(git(dir, ["remote", "get-url", "origin"]));
const isDirty = (dir) => git(dir, ["status", "--porcelain"]) !== "";

// Minimal shell tokenizer: splits a command line into segments (on && || ; | and
// newlines) of tokens, honouring single and double quotes.
function segments(command) {
  const out = [];
  let seg = [];
  let tok = "";
  let has = false;
  let quote = null;
  const pushTok = () => {
    if (has) seg.push(tok);
    tok = "";
    has = false;
  };
  const pushSeg = () => {
    pushTok();
    if (seg.length) out.push(seg);
    seg = [];
  };
  for (let i = 0; i < command.length; i++) {
    const c = command[i];
    if (quote) {
      if (c === quote) quote = null;
      else if (c === "\\" && quote === '"' && i + 1 < command.length) tok += command[++i];
      else tok += c;
      continue;
    }
    if (c === "'" || c === '"') {
      quote = c;
      has = true;
    } else if (c === "\\" && i + 1 < command.length) {
      tok += command[++i];
      has = true;
    } else if (c === " " || c === "\t") {
      pushTok();
    } else if (c === "\n" || c === ";" || c === "|" || c === "&") {
      pushSeg();
      if ((c === "&" || c === "|") && command[i + 1] === c) i++;
    } else {
      tok += c;
      has = true;
    }
  }
  pushSeg();
  return out;
}

function checkGit(args, dir) {
  // Global options before the subcommand.
  let i = 0;
  while (i < args.length && args[i].startsWith("-")) {
    const a = args[i];
    if (a === "-C") {
      dir = path.resolve(dir, args[i + 1] ?? "");
      i += 2;
    } else if (a === "-c") {
      // H4: never bypass the pre-commit hook (gitleaks is the only pre-push secret scan).
      if (/^core\.hookspath=/i.test(args[i + 1] ?? ""))
        decide("deny", "Guardrail H4: overriding core.hooksPath skips the pre-commit secret scan.");
      i += 2;
    } else i += 1;
  }
  const sub = args[i];
  const rest = args.slice(i + 1);

  // H4: never bypass the pre-commit hook (gitleaks is the only pre-push secret scan).
  if ((sub === "commit" || sub === "push") && rest.includes("--no-verify"))
    decide("deny", "Guardrail H4: --no-verify skips the pre-commit hook and its gitleaks scan.");
  if (sub === "commit") {
    const valueFlags = new Set(["-m", "-F", "-C", "-c", "-t", "--author", "--date", "--message", "--file"]);
    for (let j = 0; j < rest.length; j++) {
      const a = rest[j];
      if (valueFlags.has(a)) {
        j++;
        continue;
      }
      if (/^-[a-zA-Z]+$/.test(a)) {
        const letters = a.slice(1);
        const valueAt = letters.search(/[mFCct]/);
        const flags = valueAt === -1 ? letters : letters.slice(0, valueAt);
        if (flags.includes("n"))
          decide("deny", "Guardrail H4: git commit -n skips the pre-commit hook and its gitleaks scan.");
        if (valueAt === letters.length - 1) j++;
      }
    }
  }

  // H1: production is `main`, changed only by the "Promote dev → main" action.
  if (sub === "push") {
    const positional = [];
    for (let j = 0; j < rest.length; j++) {
      const a = rest[j];
      if (a === "-o" || a === "--push-option" || a === "--repo" || a === "--receive-pack") j++;
      else if (!a.startsWith("-")) positional.push(a);
    }
    const [remote, ...refspecs] = positional;
    const prod = isProdRepo(dir) || (remote && PROD_REPO.test(remote.replace(/\/$/, "")));
    if (prod) {
      const block = () =>
        decide(
          "deny",
          "Guardrail H1: never push to main in cms-platform. Production changes only through the " +
            "manual 'Promote dev → main' GitHub Action. Push to dev instead.",
        );
      if (rest.includes("--all") || rest.includes("--mirror")) block();
      const current = git(dir, ["rev-parse", "--abbrev-ref", "HEAD"]);
      if (refspecs.length === 0 && current === "main") block();
      for (const spec of refspecs) {
        const s = spec.replace(/^\+/, "");
        const dst = s.includes(":") ? s.slice(s.indexOf(":") + 1) : s;
        const target = dst === "HEAD" || dst === "" ? current : dst.replace(/^refs\/heads\//, "");
        if (target === "main") block();
      }
    }
  }

  // H5: don't wipe uncommitted work.
  const wipes =
    (sub === "clean" && rest.some((a) => a === "--force" || /^-[a-zA-Z]*f/.test(a))) ||
    (sub === "reset" && rest.includes("--hard")) ||
    (sub === "checkout" && rest.includes(".")) ||
    (sub === "restore" && rest.includes(".") && !(rest.includes("--staged") && !rest.includes("--worktree"))) ||
    (sub === "stash" && (rest[0] === "clear" || rest[0] === "drop"));
  if (wipes && (sub === "stash" || isDirty(dir)))
    decide(
      "ask",
      `Guardrail H5: 'git ${sub} ${rest.join(" ")}' discards uncommitted work, and this tree has ` +
        "uncommitted changes (some untracked files exist nowhere else).",
    );
}

function checkBash(command, cwd) {
  let dir = cwd;
  for (let seg of segments(command)) {
    while (seg.length && /^[A-Za-z_][A-Za-z0-9_]*=/.test(seg[0])) seg = seg.slice(1);
    if (seg[0] === "sudo" || seg[0] === "command" || seg[0] === "exec") seg = seg.slice(1);
    const [cmd, ...args] = seg;
    if (!cmd) continue;
    if (cmd === "cd" || cmd === "pushd") {
      if (args[0]) dir = path.resolve(dir, args[0].replace(/^~(?=$|\/)/, process.env.HOME ?? "~"));
      continue;
    }
    if (cmd === "git") checkGit(args, dir);

    // H1: no production deploy from a laptop; `vercel rollback` stays allowed for incidents.
    const vercelArgs =
      cmd === "vercel" ? args : cmd === "npx" ? args.slice(args.findIndex((a) => a === "vercel") + 1) : null;
    if (vercelArgs && (cmd === "vercel" || args.includes("vercel"))) {
      const prodFlag = vercelArgs.some(
        (a, j) => a === "--prod" || a === "--prod=true" || a === "--target=production" ||
          (a === "--target" && vercelArgs[j + 1] === "production"),
      );
      if (prodFlag && isProdRepo(dir))
        decide(
          "deny",
          "Guardrail H1: no production deploys from the CLI. Production changes only through the " +
            "'Promote dev → main' action. (vercel rollback is still allowed for incidents.)",
        );
    }

    // H2: one Supabase database serves local, preview and prod — writes hit production.
    const tail = seg.join(" ");
    if (
      cmd === "psql" ||
      (cmd === "supabase" && /\b(db (push|reset)|migration up)\b/.test(tail)) ||
      seg.some((a) => /apply_supabase_migration\.py$/.test(a))
    )
      decide(
        "ask",
        "Guardrail H2: this runs SQL against the one shared Supabase database, which IS production.",
      );
  }
}

// H2: execute_sql is allowed without asking only when it is clearly read-only.
function sqlIsReadOnly(sql) {
  const body = sql
    .replace(/--[^\n]*/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/'(?:[^']|'')*'/g, "''")
    .toLowerCase();
  const statements = body.split(";").map((s) => s.trim()).filter(Boolean);
  if (!statements.length) return false;
  const writes =
    /\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|comment|vacuum|call|do|copy|merge|refresh|reindex|cluster|lock|set|reset|begin|commit|security)\b/;
  const mutatingCalls =
    /\b(nextval|setval|set_config|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_advisory\w*|lo_\w+|dblink\w*)\s*\(/;
  const schemaCall = /\b[a-z_][a-z0-9_]*\s*\.\s*[a-z_][a-z0-9_]*\s*\(/;
  return statements.every(
    (s) =>
      /^(select|explain|show|with)\b/.test(s) && !writes.test(s) && !mutatingCalls.test(s) && !schemaCall.test(s),
  );
}

function checkSupabaseMcp(toolName, input) {
  const action = toolName.split("__").pop();
  // H2: one Supabase database serves local, preview and prod — writes hit production.
  if (action === "apply_migration")
    decide("ask", `Guardrail H2: applying migration '${input.name ?? "?"}' changes the production database.`);
  if (action === "pause_project") decide("ask", "Guardrail H2: pausing the Supabase project takes production down.");
  if (action === "execute_sql" && !sqlIsReadOnly(String(input.query ?? "")))
    decide("ask", "Guardrail H2: this SQL may write to the one shared Supabase database, which IS production.");
}

// H3: never edit a migration that has already been applied; add a new file instead.
function checkMigrationEdit(input, cwd) {
  const files = [input.file_path, input.notebook_path, ...(input.edits ?? []).map((e) => e.file_path)].filter(Boolean);
  for (const f of files) {
    const abs = path.resolve(cwd, String(f));
    if (/[\\/]backend[\\/]migrations[\\/][^\\/]+\.sql$/i.test(abs) && existsSync(abs))
      decide(
        "ask",
        `Guardrail H3: ${path.basename(abs)} already exists. Applied migrations are a ledger: never ` +
          "edit one, add a new migration file instead. Approve only if this migration is confirmed NOT applied.",
      );
  }
}

try {
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;
  const payload = JSON.parse(raw);
  const tool = payload.tool_name ?? "";
  const input = payload.tool_input ?? {};
  const cwd = payload.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
  if (tool === "Bash") checkBash(String(input.command ?? ""), cwd);
  else if (tool === "Edit" || tool === "Write" || tool === "MultiEdit") checkMigrationEdit(input, cwd);
  else if (/^mcp__.*supabase.*__/i.test(tool)) checkSupabaseMcp(tool, input);
} catch (err) {
  process.stderr.write(`guard.mjs: ${err?.message ?? err}\n`);
}
process.exit(0);
