// Vendored from CMS client-kit/rich-text v1.0.0 — do not edit; re-sync instead.
export const RICH_TEXT_KIT_VERSION = "1.0.0";
export { parse, decodeEntities, MARK_TAGS, INLINE_TAGS, HEADING_TAGS, BLOCK_TAGS, type RichNode, type RichElement } from "./parse";
export { safeHref, MAX_HREF_LENGTH } from "./href";
export { isHtml } from "./detect";
export { normalizeInline, normalizeRich, MAX_LIST_DEPTH } from "./normalize";
export { serialize, escapeText, escapeAttr } from "./serialize";
export { legacyToHtml } from "./legacy";
export { plainText, type PlainTextOptions } from "./plainText";
export { RichText, richTree, renderRichNodes, type RichTextProps, type RichFormat, type LinkTarget, type RenderLinkProps } from "./RichText";
export { splitRichWords, RichWords, type RichWord, type RichWordsProps } from "./splitRichWords";
