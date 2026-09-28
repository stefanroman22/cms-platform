// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
// src/normalize.ts — 1:1 port of the canonical transform in backend services/rich_text.py.
import { BLOCK_TAGS, HEADING_TAGS, INLINE_TAGS, MARK_TAGS, type RichElement, type RichNode } from "./parse";
import { safeHref } from "./href";
import { pyStrip } from "./whitespace";

export const MAX_LIST_DEPTH = 4;
// Counts strong/em/u/s/a elements enclosing the current position (independent
// of any block wrapper): beyond this, a mark/link is unwrapped rather than
// nested further. Deliberately decoupled from block structure (p/li/ul/
// blockquote) so re-parsing a canonical value never sees a different mark
// budget than the first parse did — canonicalize's idempotence relies on it.
// Mirrors backend MAX_MARK_DEPTH.
const MAX_MARK_DEPTH = 32;
const WS = /[ \t\r\n\f]+/g;
const isEl = (n: RichNode | undefined): n is RichElement => n !== undefined && typeof n !== "string";
const br = (): RichElement => ({ tag: "br", children: [] });
const el = (tag: string, children: RichNode[] = []): RichElement => ({ tag, children });

export function hasContent(nodes: RichNode[]): boolean {
  return nodes.some((n) => (typeof n === "string" ? pyStrip(n) !== "" : n.tag !== "br"));
}
// Mirrors backend _ends_with_br. Not called from inline() below — that uses
// the running `endsWithBr` flag instead (see the comment there) — kept to
// mirror the Python module's structure.
function endsWithBr(nodes: RichNode[]): boolean {
  for (let k = nodes.length - 1; k >= 0; k--) {
    const n = nodes[k];
    if (typeof n === "string") {
      if (pyStrip(n) === "") continue;
      return false;
    }
    return n.tag === "br";
  }
  return false;
}

function inline(nodes: RichNode[], inLink = false, markDepth = 0): RichNode[] {
  const out: RichNode[] = [];
  // Running state mirroring hasContent(out)/endsWithBr(out), updated as items
  // are pushed, so the block-inside-inline branch below never rescans the
  // whole (potentially large) accumulator (backend _inline's push closure).
  let hasContentFlag = false;
  let endsWithBrFlag = false;
  const push = (item: RichNode) => {
    out.push(item);
    if (typeof item === "string") {
      if (pyStrip(item) !== "") {
        hasContentFlag = true;
        endsWithBrFlag = false;
      }
      // whitespace-only strings leave hasContentFlag/endsWithBrFlag unchanged,
      // matching hasContent/endsWithBr's skip-trailing-whitespace rule
    } else {
      if (item.tag !== "br") hasContentFlag = true;
      endsWithBrFlag = item.tag === "br";
    }
  };

  for (const n of nodes) {
    if (typeof n === "string") { push(n.replace(WS, " ")); continue; }
    const tag = n.tag;
    if (tag === "br") {
      push(br());
    } else if (MARK_TAGS.has(tag)) {
      if (markDepth >= MAX_MARK_DEPTH) {
        for (const item of inline(n.children, inLink, markDepth)) push(item);
        continue;
      }
      const kids = inline(n.children, inLink, markDepth + 1);
      if (hasContent(kids)) push(el(tag, kids));
    } else if (tag === "a") {
      if (markDepth >= MAX_MARK_DEPTH) {
        for (const item of inline(n.children, true, markDepth)) push(item);
        continue;
      }
      const kids = inline(n.children, true, markDepth + 1);
      const href = inLink ? null : safeHref(n.href);
      if (href && hasContent(kids)) push({ tag: "a", href, children: kids });
      else for (const item of kids) push(item);
    } else {
      // a block element inside an inline context: flatten, separated by <br>
      const kids = tag === "hr" ? [] : inline(n.children, inLink, markDepth);
      if (tag === "hr" || hasContent(kids)) {
        if (hasContentFlag && !endsWithBrFlag) push(br());
        for (const item of kids) push(item);
        if (!endsWithBrFlag) push(br());
      }
    }
  }
  return out;
}

function tidy(nodes: RichNode[]): RichNode[] {
  const res: RichNode[] = [];
  let buf: string[] = [];
  const flush = () => {
    if (!buf.length) return;
    let s = buf.join("").replace(WS, " ");
    buf = [];
    const last = res.length ? res[res.length - 1] : undefined;
    if (isEl(last) && last.tag === "br") s = s.replace(/^ +/, "");
    if (s) res.push(s);
  };
  for (const n of nodes) {
    if (typeof n === "string") { buf.push(n); continue; }
    flush();
    if (n.tag === "br" && res.length && typeof res[res.length - 1] === "string") {
      const t = (res[res.length - 1] as string).replace(/ +$/, "");
      if (t) res[res.length - 1] = t;
      else res.pop();
    }
    res.push(n);
  }
  flush();
  return res;
}
const dropEdge = (n: RichNode) => (typeof n === "string" ? pyStrip(n) === "" : n.tag === "br");
function trimEdges(nodes: RichNode[]): RichNode[] {
  const res = tidy(nodes);
  while (res.length && dropEdge(res[0])) res.shift();
  while (res.length && dropEdge(res[res.length - 1])) res.pop();
  if (typeof res[0] === "string") res[0] = res[0].replace(/^ +/, "");
  const l = res.length - 1;
  if (l >= 0 && typeof res[l] === "string") res[l] = (res[l] as string).replace(/ +$/, "");
  return res;
}
const isEmptyP = (n: RichElement) => n.tag === "p" && !hasContent(n.children);
function trimEmptyEdges(bs: RichElement[]): RichElement[] {
  let s = 0;
  let e = bs.length;
  while (s < e && isEmptyP(bs[s])) s++;
  while (e > s && isEmptyP(bs[e - 1])) e--;
  return bs.slice(s, e);
}
function paragraphNodes(children: RichNode[], depth: number): RichElement[] {
  if (children.some((c) => isEl(c) && BLOCK_TAGS.has(c.tag))) return blocks(children, depth);
  return [el("p", trimEdges(inline(children)))];
}
function blocks(nodes: RichNode[], depth: number): RichElement[] {
  const out: RichElement[] = [];
  let pending: RichNode[] = [];
  const flush = () => {
    if (pending.length) {
      const kids = trimEdges(inline(pending));
      if (hasContent(kids)) out.push(el("p", kids));
      pending = [];
    }
  };
  for (const n of nodes) {
    if (typeof n === "string" || INLINE_TAGS.has(n.tag)) { pending.push(n); continue; }
    flush();
    const tag = n.tag;
    if (tag === "p") out.push(...paragraphNodes(n.children, depth));
    else if (HEADING_TAGS.has(tag)) {
      const kids = trimEdges(inline(n.children));
      if (hasContent(kids)) out.push(el(tag, kids));
    } else if (tag === "hr") out.push(el("hr"));
    else if (tag === "ul" || tag === "ol") out.push(...list(n, depth + 1));
    else if (tag === "li") out.push(...list(el("ul", [n]), depth + 1));
    else if (tag === "blockquote") {
      const inner: RichElement[] = [];
      for (const b of trimEmptyEdges(blocks(n.children, depth))) {
        inner.push(...(b.tag === "blockquote" ? (b.children as RichElement[]) : [b]));
      }
      if (inner.length) out.push(el("blockquote", inner));
    }
  }
  flush();
  return out;
}
function li(children: RichNode[], depth: number): RichElement {
  const kept: RichElement[] = [];
  for (const b of blocks(children, depth)) {
    if (b.tag === "p" || b.tag === "ul" || b.tag === "ol") kept.push(b);
    else if (HEADING_TAGS.has(b.tag)) kept.push(el("p", b.children));
    else if (b.tag === "blockquote") {
      kept.push(...(b.children as RichElement[]).filter((x) => x.tag === "p" || x.tag === "ul" || x.tag === "ol"));
    }
  }
  if (!kept.length || kept[0].tag !== "p") kept.unshift(el("p"));
  return el("li", kept);
}
const liHasContent = (item: RichElement) =>
  item.children.some((c) => isEl(c) && (c.tag === "ul" || c.tag === "ol" || (c.tag === "p" && hasContent(c.children))));
function list(node: RichElement, depth: number): RichElement[] {
  let items: RichElement[] = [];
  for (const c of node.children) {
    if (typeof c === "string") { if (pyStrip(c)) items.push(li([c], depth)); continue; }
    if (c.tag === "li") items.push(li(c.children, depth));
    else if ((c.tag === "ul" || c.tag === "ol") && items.length) items[items.length - 1].children.push(...list(c, depth + 1));
    else items.push(li([c], depth));
  }
  items = items.filter(liHasContent);
  if (!items.length) return [];
  if (depth > MAX_LIST_DEPTH) return items.flatMap((x) => x.children as RichElement[]);
  return [el(node.tag, items)];
}

export function normalizeInline(nodes: RichNode[]): RichNode[] {
  return trimEdges(inline(nodes));
}
export function normalizeRich(nodes: RichNode[]): RichElement[] {
  return trimEmptyEdges(blocks(nodes, 0));
}
