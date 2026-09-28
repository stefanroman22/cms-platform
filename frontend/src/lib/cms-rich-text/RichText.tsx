// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
import { Fragment, createElement, type ElementType, type ReactNode } from "react";
import { isHtml } from "./detect";
import { legacyToHtml } from "./legacy";
import { normalizeInline, normalizeRich } from "./normalize";
import { parse, type RichElement, type RichNode } from "./parse";

export type RichFormat = "inline" | "rich";
export type LinkTarget = "auto" | "self" | "blank";
export interface RenderLinkProps { href: string; external: boolean; children: ReactNode }

export interface RichTextProps {
  value?: string | null;
  format?: RichFormat;
  as?: ElementType;
  className?: string;
  id?: string;
  /** Shift h2–h4 by this many levels (e.g. 1 inside cards). Clamped to h1–h6. */
  headingOffset?: number;
  /** false renders links as <span class="cms-rich-link"> — use inside already-clickable elements. */
  links?: boolean;
  linkTarget?: LinkTarget;
  /** Render internal (/path, #hash) links with the site's router link. */
  renderLink?: (props: RenderLinkProps) => ReactNode;
}

/** Normalized node tree for a CMS value (spec §4.4: inline = HTML fragment; tag-free rich = legacy). */
export function richTree(value: string | null | undefined, format: RichFormat = "rich"): RichNode[] {
  if (typeof value !== "string" || !value.trim()) return [];
  const src = format === "rich" && !isHtml(value) ? legacyToHtml(value, "rich") : value;
  const root = parse(src);
  return format === "inline" ? normalizeInline(root.children) : normalizeRich(root.children);
}

interface Ctx { headingOffset: number; links: boolean; linkTarget: LinkTarget; renderLink?: RichTextProps["renderLink"] }
const EXTERNAL = /^https?:\/\//i;

export function renderRichNodes(nodes: RichNode[], ctx: Ctx): ReactNode[] {
  return nodes.map((n, i) => renderNode(n, i, ctx));
}

function renderAnchor(n: RichElement, key: number, kids: ReactNode[], ctx: Ctx): ReactNode {
  const href = n.href ?? "";
  const external = EXTERNAL.test(href);
  if (!ctx.links) return <span key={key} className="cms-rich-link">{kids}</span>;
  if (ctx.renderLink && !external && (href.startsWith("/") || href.startsWith("#"))) {
    return <Fragment key={key}>{ctx.renderLink({ href, external, children: kids })}</Fragment>;
  }
  const blank = ctx.linkTarget === "blank" || (ctx.linkTarget === "auto" && external);
  return blank ? (
    <a key={key} href={href} target="_blank" rel="noopener noreferrer">{kids}</a>
  ) : (
    <a key={key} href={href}>{kids}</a>
  );
}

function renderNode(n: RichNode, key: number, ctx: Ctx): ReactNode {
  if (typeof n === "string") return n;
  const kids = renderRichNodes(n.children, ctx);
  switch (n.tag) {
    case "br": return <br key={key} />;
    case "hr": return <hr key={key} />;
    case "a": return renderAnchor(n, key, kids, ctx);
    case "h2":
    case "h3":
    case "h4": {
      const level = Math.min(6, Math.max(1, Number(n.tag[1]) + ctx.headingOffset));
      return createElement(`h${level}`, { key }, ...kids);
    }
    default:
      return createElement(n.tag, { key }, ...kids);
  }
}

/** Renders a CMS inline/rich value safely (no innerHTML) as semantic elements themed by --cms-rich-* vars.
 *  Uses no hooks, so it works as a Next.js Server Component and in client components. */
export function RichText({
  value, format = "rich", as, className, id, headingOffset = 0, links = true, linkTarget = "auto", renderLink,
}: RichTextProps) {
  const nodes = richTree(value, format);
  if (!nodes.length) return null;
  const Tag: ElementType = as ?? (format === "inline" ? "span" : "div");
  const cls = ["cms-rich", format === "inline" ? "cms-rich--inline" : "", className ?? ""].filter(Boolean).join(" ");
  // createElement, not JSX: a generic `ElementType`-typed tag makes some @types/react versions
  // narrow the JSX children prop to `never` (DefinitelyTyped ElementType/children inference gap).
  return createElement(Tag, { className: cls, id }, renderRichNodes(nodes, { headingOffset, links, linkTarget, renderLink }));
}
