import { beforeAll, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Editor } from "@tiptap/react";
import { RichTextEditor } from "../RichTextEditor";

beforeAll(() => {
  // ProseMirror layout APIs jsdom lacks.
  Range.prototype.getBoundingClientRect = () =>
    ({
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      toJSON: () => ({}),
    }) as DOMRect;
  Range.prototype.getClientRects = () =>
    ({
      length: 0,
      item: () => null,
      [Symbol.iterator]: [][Symbol.iterator],
    }) as unknown as DOMRectList;
  document.elementFromPoint = () => null;
  // jsdom has no ClipboardEvent constructor; `view.pasteHTML(html)` builds one
  // internally (`new ClipboardEvent("paste")`) when no event is passed in.
  if (typeof ClipboardEvent === "undefined") {
    class FakeClipboardEvent extends Event {
      clipboardData: DataTransfer | null;
      constructor(
        type: string,
        eventInitDict?: EventInit & { clipboardData?: DataTransfer | null }
      ) {
        const { clipboardData, ...init } = eventInitDict ?? {};
        super(type, init);
        this.clipboardData = clipboardData ?? null;
      }
    }
    (globalThis as unknown as { ClipboardEvent: unknown }).ClipboardEvent = FakeClipboardEvent;
  }
});

async function setup(props: Partial<Parameters<typeof RichTextEditor>[0]> = {}) {
  let editor: Editor | undefined;
  const onChange = vi.fn();
  render(
    <RichTextEditor
      value=""
      onChange={onChange}
      mode="rich"
      label="Body"
      onReady={(e) => {
        editor = e;
      }}
      {...props}
    />
  );
  await waitFor(() => expect(editor).toBeDefined());
  return { editor: editor!, onChange };
}

describe("RichTextEditor", () => {
  it("loads stored HTML and exposes an accessible textbox", async () => {
    await setup({ value: "<p>Hello <strong>x</strong></p>" });
    const box = screen.getByRole("textbox", { name: "Body" });
    expect(box.innerHTML).toContain("<strong>x</strong>");
  });

  it("bold button toggles bold and emits stored HTML", async () => {
    const { editor, onChange } = await setup({ value: "<p>word</p>" });
    act(() => {
      editor.commands.selectAll();
    });
    await userEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(onChange).toHaveBeenLastCalledWith("<p><strong>word</strong></p>");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Bold" })).toHaveAttribute("aria-pressed", "true")
    );
  });

  it("emptying the editor stores an empty string", async () => {
    const { editor, onChange } = await setup({ value: "<p>x</p>" });
    act(() => {
      editor.commands.clearContent(true);
    });
    expect(onChange).toHaveBeenLastCalledWith("");
  });

  it("inline mode: no lists/headings in the toolbar and Enter inserts a line break", async () => {
    const { editor, onChange } = await setup({ mode: "inline", value: "a", label: "Title" });
    expect(screen.queryByRole("button", { name: "Bullet list" })).toBeNull();
    expect(screen.queryByLabelText("Text style")).toBeNull();
    act(() => {
      editor.commands.focus("end");
      editor.commands.keyboardShortcut("Enter");
      editor.commands.insertContent("b");
    });
    expect(onChange).toHaveBeenLastCalledWith("a<br>b");
  });

  it("Google Docs paste keeps real bold, drops the wrapper bold and colours", async () => {
    const { editor, onChange } = await setup();
    act(() => {
      editor.view.pasteHTML(
        '<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-1"><span style="font-weight:700;color:#ff0000">Bold</span><span style="font-weight:400;color:#00ff00"> plain</span></b>'
      );
    });
    expect(onChange).toHaveBeenLastCalledWith("<p><strong>Bold</strong> plain</p>");
  });

  it("inline paste of several paragraphs becomes line breaks", async () => {
    const { editor, onChange } = await setup({ mode: "inline", label: "Title" });
    act(() => {
      editor.view.pasteHTML("<p>one</p><ul><li>two</li></ul>");
    });
    expect(onChange).toHaveBeenLastCalledWith("one<br>two");
  });

  it("link popover validates and applies", async () => {
    const { editor, onChange } = await setup({ value: "<p>site</p>" });
    act(() => {
      editor.commands.selectAll();
    });
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    const input = screen.getByLabelText("Link address");
    await userEvent.type(input, "javascript:alert(1){enter}");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await userEvent.clear(input);
    await userEvent.type(input, "example.com{enter}");
    expect(onChange).toHaveBeenLastCalledWith('<p><a href="https://example.com">site</a></p>');
  });

  it("shows the counter near the limit", async () => {
    await setup({ mode: "inline", value: "x".repeat(1700), label: "Title" });
    expect(await screen.findByText(/1,700 \/ 2,000/)).toBeInTheDocument();
  });
});
