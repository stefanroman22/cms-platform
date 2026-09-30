import { beforeAll, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
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
  const utils = render(
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
  return { editor: editor!, onChange, rerender: utils.rerender };
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

  it("text style uses the app dropdown and applies a heading", async () => {
    const { editor } = await setup({ mode: "rich", value: "<p>x</p>" });
    act(() => {
      editor.commands.focus("end");
    });
    await userEvent.click(await screen.findByLabelText("Text style"));
    await userEvent.click(screen.getByRole("option", { name: "Heading 2" }));
    expect(editor.getHTML()).toContain("<h2>");
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

  it("shows the spec's exact wording once over the limit", async () => {
    await setup({ mode: "inline", value: "x".repeat(2001), label: "Title" });
    expect(await screen.findByText(/Too long — the save will be rejected/)).toBeInTheDocument();
  });

  it("does not fire onChange on mount, or merely from toggling disabled", async () => {
    const onChange = vi.fn();
    let editor: Editor | undefined;
    const onReady = (e: Editor) => {
      editor = e;
    };
    const { rerender } = render(
      <RichTextEditor
        value="<ul><li>a</li></ul>"
        onChange={onChange}
        mode="rich"
        label="Body"
        onReady={onReady}
      />
    );
    await waitFor(() => expect(editor).toBeDefined());
    expect(onChange).not.toHaveBeenCalled();

    rerender(
      <RichTextEditor
        value="<ul><li>a</li></ul>"
        onChange={onChange}
        mode="rich"
        label="Body"
        disabled
        onReady={onReady}
      />
    );
    expect(onChange).not.toHaveBeenCalled();

    rerender(
      <RichTextEditor
        value="<ul><li>a</li></ul>"
        onChange={onChange}
        mode="rich"
        label="Body"
        disabled={false}
        onReady={onReady}
      />
    );
    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not fire onChange on mount for a legacy (markdown) value", async () => {
    const { onChange } = await setup({ value: "**legacy**" });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("pasted link keeps only href — target/rel/class/title are stripped", async () => {
    const { editor, onChange } = await setup();
    act(() => {
      editor.view.pasteHTML(
        '<a href="https://x.ro" target="_blank" rel="noopener" class="c" title="t">x</a>'
      );
    });
    expect(onChange).toHaveBeenLastCalledWith('<p><a href="https://x.ro">x</a></p>');
  });

  it("inline mode: multi-line plain-text paste keeps every line as a break (none dropped)", async () => {
    const { editor, onChange } = await setup({ mode: "inline", label: "Title" });
    act(() => {
      editor.view.pasteText("one\ntwo\n\nthree");
    });
    expect(onChange).toHaveBeenLastCalledWith("one<br>two<br><br>three");
    expect(editor.getHTML().match(/<p>/g)?.length).toBe(1);
  });

  it("rich mode: multi-line plain-text paste is unchanged (separate paragraphs)", async () => {
    const { editor, onChange } = await setup();
    act(() => {
      editor.view.pasteText("one\n\ntwo");
    });
    expect(onChange).toHaveBeenLastCalledWith("<p>one</p><p>two</p>");
  });

  it("link popover keeps a typed value across an unrelated parent re-render", async () => {
    let editor: Editor | undefined;
    const onChange = vi.fn();
    const onReady = (e: Editor) => {
      editor = e;
    };
    const { rerender } = render(
      <RichTextEditor
        value="<p>site</p>"
        onChange={onChange}
        mode="rich"
        label="Body"
        onReady={onReady}
      />
    );
    await waitFor(() => expect(editor).toBeDefined());
    act(() => {
      editor!.commands.selectAll();
    });
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    const input = screen.getByLabelText("Link address");
    await userEvent.type(input, "exa");

    // Simulate the Toolbar re-rendering mid-typing (its `useEditorState`
    // selector recomputing, or any other unrelated parent re-render) — it
    // passes LinkPopover a brand-new `onClose` arrow function every time.
    rerender(
      <RichTextEditor
        value="<p>site</p>"
        onChange={onChange}
        mode="rich"
        label="Body"
        onReady={onReady}
      />
    );

    await userEvent.type(input, "mple.com");
    expect(input).toHaveValue("example.com");
  });

  it("toolbar uses a real roving tabindex: exactly one control is Tab-reachable at a time", async () => {
    const { editor } = await setup({ value: "<p>x</p>" });
    // useEditorState's snapshot only updates on the editor's first
    // "transaction" event (tiptap/react's EditorStateManager), same as every
    // other test here that queries toolbar buttons right after setup().
    act(() => {
      editor.commands.selectAll();
    });
    const toolbar = screen.getByRole("toolbar");
    // Disabled controls (Undo/Redo/Remove-link, with nothing to undo or no
    // link yet) are never in the browser's Tab order regardless of their
    // tabIndex property, and the roving-tabindex logic correctly ignores
    // them (same `:not(:disabled)` selector as the component) — so only
    // enabled controls are counted here.
    const controls = within(toolbar)
      .getAllByRole("button")
      .concat(within(toolbar).queryAllByRole("combobox"))
      .filter((el) => !el.hasAttribute("disabled"));
    expect(controls.filter((el) => el.tabIndex === 0)).toHaveLength(1);

    const bold = screen.getByRole("button", { name: "Bold" });
    bold.focus();
    expect(bold.tabIndex).toBe(0);
    expect(controls.filter((el) => el !== bold && el.tabIndex === 0)).toHaveLength(0);
  });

  it("does not lose the remembered Tab stop when a previously-disabled control becomes enabled", async () => {
    const { editor } = await setup({ value: "<p>word</p>" });
    act(() => {
      editor.commands.selectAll();
    });
    const bold = screen.getByRole("button", { name: "Bold" });
    bold.focus();
    expect(bold.tabIndex).toBe(0);

    // An edit: enables Undo, which was disabled (and so excluded from the
    // roving list, keeping the browser's native default tabIndex) until now.
    // Bold — not Undo — must remain the one Tab-reachable control.
    act(() => {
      editor.commands.toggleBold();
    });

    const toolbar = screen.getByRole("toolbar");
    const enabledControls = within(toolbar)
      .getAllByRole("button")
      .concat(within(toolbar).queryAllByRole("combobox"))
      .filter((el) => !el.hasAttribute("disabled"));
    expect(enabledControls.filter((el) => el.tabIndex === 0)).toEqual([bold]);
  });

  it("toolbar's sticky wrapper sits directly in the tall editor container (has room to stick)", async () => {
    const { editor } = await setup({ value: "<p>x</p>" });
    act(() => {
      editor.commands.selectAll();
    });
    const toolbar = screen.getByRole("toolbar");
    const stickyWrapper = toolbar.parentElement;
    expect(stickyWrapper).not.toBeNull();
    expect(stickyWrapper!.className).toMatch(/\bsticky\b/);
    // Its own parent must be the whole (tall) editor container — the one
    // that also holds EditorContent below it — not a wrapper sized to the
    // toolbar alone, which would give `sticky` nowhere to travel.
    expect(stickyWrapper!.parentElement).toHaveAttribute("data-mode", "rich");
  });

  it("arrow keys inside the open link popover stay inside it (not hijacked by the toolbar)", async () => {
    const { editor } = await setup({ value: "<p>site</p>" });
    act(() => {
      editor.commands.selectAll();
    });
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    const input = screen.getByLabelText("Link address");
    expect(input).toHaveFocus();
    await userEvent.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(input).toHaveFocus();
  });
});

describe("RichTextEditor render cost", () => {
  it("does not call editor.setOptions when the parent re-renders with a new value/onChange", async () => {
    let editor: Editor | undefined;
    const { rerender } = render(
      <RichTextEditor
        value="<p>a</p>"
        onChange={() => {}}
        mode="rich"
        label="Body"
        onReady={(e) => (editor = e)}
      />
    );
    await waitFor(() => expect(editor).toBeDefined());
    const spy = vi.spyOn(editor!, "setOptions");
    for (const v of ["<p>ab</p>", "<p>abc</p>", "<p>abcd</p>"]) {
      rerender(
        <RichTextEditor
          value={v}
          onChange={() => {}}
          mode="rich"
          label="Body"
          onReady={(e) => (editor = e)}
        />
      );
    }
    expect(spy).not.toHaveBeenCalled();
  });

  it("still reconfigures when the placeholder changes", async () => {
    let editor: Editor | undefined;
    const onReady = (e: Editor) => (editor = e);
    const { rerender } = render(
      <RichTextEditor
        value=""
        onChange={() => {}}
        mode="rich"
        label="Body"
        placeholder="One"
        onReady={onReady}
      />
    );
    await waitFor(() => expect(editor).toBeDefined());
    const spy = vi.spyOn(editor!, "setOptions");
    rerender(
      <RichTextEditor
        value=""
        onChange={() => {}}
        mode="rich"
        label="Body"
        placeholder="Two"
        onReady={onReady}
      />
    );
    expect(spy).toHaveBeenCalled();
  });
});
