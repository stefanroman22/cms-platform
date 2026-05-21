"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import {
  Bold,
  Code,
  Heading1,
  Heading2,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Redo2,
  Undo2,
} from "lucide-react";

interface BtnProps {
  active?: boolean;
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}

function Btn({ active, onClick, title, children }: BtnProps) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`h-7 w-7 inline-flex items-center justify-center rounded-md text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer transition-colors ${
        active ? "ring-2 ring-zinc-300 dark:ring-zinc-700 bg-zinc-100 dark:bg-zinc-800" : ""
      }`}
    >
      {children}
    </button>
  );
}

interface Props {
  value: string;
  onChange: (html: string) => void;
}

export function DesignPromptEditor({ value, onChange }: Props) {
  const editor = useEditor({
    extensions: [StarterKit, Link.configure({ openOnClick: false, autolink: true })],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
    editorProps: {
      attributes: {
        class:
          "prose prose-sm prose-zinc dark:prose-invert max-w-none focus:outline-none min-h-[8rem]",
      },
    },
    immediatelyRender: false,
  });

  if (!editor) return null;

  function promptLink() {
    if (!editor) return;
    const prev = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("URL", prev ?? "https://");
    if (url === null) return;
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-0.5 sticky top-0 bg-zinc-50 dark:bg-zinc-900 py-1 z-10">
        <Btn
          title="Bold"
          active={editor.isActive("bold")}
          onClick={() => editor.chain().focus().toggleBold().run()}
        >
          <Bold className="h-3.5 w-3.5" />
        </Btn>
        <Btn
          title="Italic"
          active={editor.isActive("italic")}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        >
          <Italic className="h-3.5 w-3.5" />
        </Btn>
        <Btn
          title="Heading 1"
          active={editor.isActive("heading", { level: 1 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        >
          <Heading1 className="h-3.5 w-3.5" />
        </Btn>
        <Btn
          title="Heading 2"
          active={editor.isActive("heading", { level: 2 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        >
          <Heading2 className="h-3.5 w-3.5" />
        </Btn>
        <Btn
          title="Bullet list"
          active={editor.isActive("bulletList")}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        >
          <List className="h-3.5 w-3.5" />
        </Btn>
        <Btn
          title="Numbered list"
          active={editor.isActive("orderedList")}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
        >
          <ListOrdered className="h-3.5 w-3.5" />
        </Btn>
        <Btn
          title="Code block"
          active={editor.isActive("codeBlock")}
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        >
          <Code className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Link" active={editor.isActive("link")} onClick={promptLink}>
          <LinkIcon className="h-3.5 w-3.5" />
        </Btn>
        <div className="mx-1 h-4 w-px bg-zinc-200 dark:bg-zinc-700" />
        <Btn title="Undo" onClick={() => editor.chain().focus().undo().run()}>
          <Undo2 className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Redo" onClick={() => editor.chain().focus().redo().run()}>
          <Redo2 className="h-3.5 w-3.5" />
        </Btn>
      </div>
      <div className="rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 p-3">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
