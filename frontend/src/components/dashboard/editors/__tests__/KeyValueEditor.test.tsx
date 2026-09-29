import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KeyValueEditor } from "../KeyValueEditor";
import { convertValue } from "@/components/dashboard/rich-text/ContentField";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ label, mode }: { label: string; mode: string }) => (
    <div role="textbox" aria-label={label} data-mode={mode} />
  ),
}));

const initial = {
  entries: { phone: "+40 7", about: "We &amp; you" },
  _formats: { about: "inline" },
};

describe("KeyValueEditor", () => {
  it("keeps _formats when rows are edited", async () => {
    const onChange = vi.fn();
    render(<KeyValueEditor initialContent={initial} onChange={onChange} richText />);
    await userEvent.type(screen.getByDisplayValue("+40 7"), "0");
    expect(onChange).toHaveBeenLastCalledWith({
      entries: { phone: "+40 70", about: "We &amp; you" },
      _formats: { about: "inline" },
    });
  });
  it("renders the inline editor for inline entries and inputs for plain ones", () => {
    render(<KeyValueEditor initialContent={initial} onChange={() => {}} richText />);
    expect(screen.getByRole("textbox", { name: "about" })).toHaveAttribute("data-mode", "inline");
    expect(screen.getByDisplayValue("+40 7").tagName).toBe("INPUT");
  });
  it("non-admins get no format select; admins do", () => {
    const { rerender } = render(
      <KeyValueEditor initialContent={initial} onChange={() => {}} richText />
    );
    expect(screen.queryByLabelText("Format of phone")).toBeNull();
    rerender(
      <KeyValueEditor initialContent={initial} onChange={() => {}} richText canEditStructure />
    );
    expect(screen.getByLabelText("Format of phone")).toBeInTheDocument();
  });
  it("deleting a row drops its format", async () => {
    const onChange = vi.fn();
    render(<KeyValueEditor initialContent={initial} onChange={onChange} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Remove row" })[1]);
    expect(onChange).toHaveBeenLastCalledWith({ entries: { phone: "+40 7" }, _formats: {} });
  });
});

describe("KeyValueEditor format on the row", () => {
  it("clearing and retyping a key keeps its format", async () => {
    const onChange = vi.fn();
    render(
      <KeyValueEditor initialContent={initial} onChange={onChange} richText canEditStructure />
    );
    const key = screen.getByDisplayValue("about");
    await userEvent.clear(key);
    await userEvent.type(key, "about");
    expect(onChange).toHaveBeenLastCalledWith({
      entries: { phone: "+40 7", about: "We &amp; you" },
      _formats: { about: "inline" },
    });
  });
  it("admin rename keeps the format", async () => {
    const onChange = vi.fn();
    render(
      <KeyValueEditor initialContent={initial} onChange={onChange} richText canEditStructure />
    );
    await userEvent.type(screen.getByDisplayValue("about"), "2");
    expect(onChange).toHaveBeenLastCalledWith({
      entries: { phone: "+40 7", about2: "We &amp; you" },
      _formats: { about2: "inline" },
    });
  });
  it("non-admin key is read-only for formatted entries, editable for plain", () => {
    render(<KeyValueEditor initialContent={initial} onChange={() => {}} richText />);
    expect(screen.getByDisplayValue("about")).toHaveAttribute("readonly");
    expect(screen.getByDisplayValue("phone")).not.toHaveAttribute("readonly");
  });
  it("admin format change converts the value and emits it", async () => {
    const onChange = vi.fn();
    render(
      <KeyValueEditor initialContent={initial} onChange={onChange} richText canEditStructure />
    );
    await userEvent.selectOptions(screen.getByLabelText("Format of phone"), "inline");
    expect(onChange).toHaveBeenLastCalledWith({
      entries: { phone: "+40 7", about: "We &amp; you" },
      _formats: { phone: "inline", about: "inline" },
    });
    expect(screen.getByRole("textbox", { name: "phone" })).toHaveAttribute("data-mode", "inline");
  });
  it("version 0 emits only entries", async () => {
    const onChange = vi.fn();
    render(<KeyValueEditor initialContent={{ entries: { a: "1" } }} onChange={onChange} />);
    await userEvent.type(screen.getByDisplayValue("1"), "2");
    expect(onChange).toHaveBeenLastCalledWith({ entries: { a: "12" } });
  });
});

describe("convertValue", () => {
  it.each([
    ["A & B", "plain", "inline", "A &amp; B"],
    ["a\nb", "plain", "rich", "<p>a<br>b</p>"],
    ["A &amp; <strong>B</strong>", "inline", "plain", "A & B"],
    ["A <em>B</em>", "inline", "rich", "<p>A <em>B</em></p>"],
    ["<p>a</p><p>b &amp; c</p>", "rich", "inline", "a<br>b &amp; c"],
  ])("%s %s→%s", (v, f, t, e) => expect(convertValue(v, f as never, t as never)).toBe(e));
});
