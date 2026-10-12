import { Extension } from "@tiptap/core";
import Document from "@tiptap/extension-document";
import { Color, FontFamily, FontSize, TextStyle } from "@tiptap/extension-text-style";
import StarterKit from "@tiptap/starter-kit";
import { Placeholder } from "@tiptap/extensions";
import { safeHref } from "@/lib/cms-rich-text";

// Colour, font and size marks (ADR-0011) are stored as one canonical span via toStored.
const textStyle = [TextStyle, Color, FontFamily, FontSize];

const link = {
  openOnClick: false,
  autolink: true,
  linkOnPaste: true,
  defaultProtocol: "https",
  protocols: ["mailto", "tel"],
  HTMLAttributes: { target: null, rel: null },
  isAllowedUri: (url: string) => safeHref(url) !== null,
};

export function richExtensions(placeholder = "") {
  return [
    StarterKit.configure({ heading: { levels: [2, 3, 4] }, code: false, codeBlock: false, link }),
    ...textStyle,
    Placeholder.configure({ placeholder }),
  ];
}

/** Single-paragraph document: titles and short fields. Enter inserts a line break. */
const InlineDocument = Document.extend({ content: "paragraph" });
const InlineEnter = Extension.create({
  name: "inlineEnter",
  priority: 1000,
  addKeyboardShortcuts() {
    return { Enter: () => this.editor.commands.setHardBreak() };
  },
});

export function inlineExtensions(placeholder = "") {
  return [
    StarterKit.configure({
      document: false,
      heading: false,
      bulletList: false,
      orderedList: false,
      listItem: false,
      listKeymap: false,
      blockquote: false,
      horizontalRule: false,
      code: false,
      codeBlock: false,
      trailingNode: false,
      link,
    }),
    ...textStyle,
    InlineDocument,
    InlineEnter,
    Placeholder.configure({ placeholder }),
  ];
}
