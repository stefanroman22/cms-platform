// Vendored from CMS client-kit/rich-text v1.1.0 — do not edit; re-sync instead.
export const RICH_TEXT_KIT_VERSION = "1.1.0";
export { parse, decodeEntities, MARK_TAGS, INLINE_TAGS, HEADING_TAGS, BLOCK_TAGS, type RichNode, type RichElement } from "./parse";
export { safeHref, MAX_HREF_LENGTH } from "./href";
export { isHtml } from "./detect";
export { normalizeInline, normalizeRich, MAX_LIST_DEPTH } from "./normalize";
export { serialize, escapeText, escapeAttr } from "./serialize";
export { canonicalStyle, parseStyle } from "./style";
export { legacyToHtml } from "./legacy";
export { plainText, type PlainTextOptions } from "./plainText";
export { RichText, richTree, renderRichNodes, type RichTextProps, type RichFormat, type LinkTarget, type RenderLinkProps } from "./RichText";
export { splitRichWords, RichWords, type RichWord, type RichWordsProps } from "./splitRichWords";
export {
  FONT_FAMILY_RE, readTheme, googleFontsHref, fontStack, themeCss, relativeLuminance, contrastRatio,
  recommendIconColors, readIcon, type ThemeColor, type ThemeFont, type CmsTheme, type CmsIconValue,
} from "./theme";
export { ThemeStyles } from "./ThemeStyles";
export { CmsIcon, type CmsIconProps } from "./CmsIcon";
