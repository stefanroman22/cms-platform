// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
import { Fragment, createElement, type ElementType, type ReactNode } from "react";
import { isHtml } from "./detect";
import { legacyToHtml } from "./legacy";
import { normalizeInline } from "./normalize";
import { parse, type RichNode } from "./parse";
import type { RichFormat } from "./RichText";

export interface RichWord { key: string; text: string; node: ReactNode; breakBefore: boolean }
type Mark = { tag: string; href?: string | null };
const EXTERNAL = /^https?:\/\//i;

function wrap(text: string, marks: Mark[]): ReactNode {
  let node: ReactNode = text;
  for (let k = marks.length - 1; k >= 0; k--) {
    const m = marks[k];
    if (m.tag === "a") {
      const href = m.href ?? "";
      node = EXTERNAL.test(href)
        ? createElement("a", { href, target: "_blank", rel: "noopener noreferrer" }, node)
        : createElement("a", { href }, node);
    } else {
      node = createElement(m.tag, null, node);
    }
  }
  return node;
}

/** Word tokens of a CMS value with their formatting, for per-word animations. Always flattened to inline. */
export function splitRichWords(value: string | null | undefined, format: RichFormat = "inline"): RichWord[] {
  if (typeof value !== "string" || !value.trim()) return [];
  const html = format === "rich" && !isHtml(value) ? legacyToHtml(value, "rich") : value;
  const nodes = normalizeInline(parse(html).children);
  const words: RichWord[] = [];
  let pendingBreak = false;
  let glue = false; // the previous text ended mid-word
  const walk = (list: RichNode[], marks: Mark[]) => {
    for (const n of list) {
      if (typeof n === "string") {
        n.split(/(\s+)/).forEach((piece, idx) => {
          if (!piece) return;
          if (/^\s+$/.test(piece)) { glue = false; return; }
          const node = wrap(piece, marks);
          const last = words[words.length - 1];
          if (glue && idx === 0 && last && !pendingBreak) {
            last.text += piece;
            last.node = createElement(Fragment, null, last.node, node);
          } else {
            words.push({ key: `w${words.length}`, text: piece, node, breakBefore: pendingBreak });
            pendingBreak = false;
          }
          glue = true;
        });
      } else if (n.tag === "br") {
        pendingBreak = true;
        glue = false;
      } else {
        walk(n.children, [...marks, { tag: n.tag, href: n.href }]);
      }
    }
  };
  walk(nodes, []);
  return words;
}

export interface RichWordsProps {
  value?: string | null;
  format?: RichFormat;
  renderWord: (word: RichWord, index: number) => ReactNode;
  as?: ElementType;
  className?: string;
}

export function RichWords({ value, format = "inline", renderWord, as, className }: RichWordsProps) {
  const words = splitRichWords(value, format);
  if (!words.length) return null;
  const Tag: ElementType = as ?? "span";
  const cls = ["cms-rich", "cms-rich--inline", className ?? ""].filter(Boolean).join(" ");
  // createElement, not JSX: a generic `ElementType`-typed tag makes some @types/react versions
  // narrow the JSX children prop to `never` (DefinitelyTyped ElementType/children inference gap).
  return createElement(
    Tag,
    { className: cls },
    words.map((w, i) => (
      <Fragment key={w.key}>
        {w.breakBefore ? <br /> : i > 0 ? " " : null}
        {renderWord(w, i)}
      </Fragment>
    )),
  );
}
