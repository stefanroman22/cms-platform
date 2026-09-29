import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TextBlockEditor } from "../TextBlockEditor";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ label, value, mode }: { label: string; value: string; mode: string }) => (
    <div role="textbox" aria-label={label} data-mode={mode}>
      {value}
    </div>
  ),
}));

describe("TextBlockEditor", () => {
  it("version 0 keeps the legacy input and textarea", () => {
    render(<TextBlockEditor initialContent={{ title: "t", body: "b" }} onChange={() => {}} />);
    expect(screen.getByDisplayValue("t").tagName).toBe("INPUT");
    expect(screen.getByDisplayValue("b").tagName).toBe("TEXTAREA");
  });
  it("version 1 renders inline title and rich body editors", () => {
    render(
      <TextBlockEditor
        initialContent={{ title: "t", body: "<p>b</p>" }}
        onChange={() => {}}
        richText
        fieldFormats={{ title: "inline", body: "rich" }}
      />
    );
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveAttribute("data-mode", "inline");
    expect(screen.getByRole("textbox", { name: "Body" })).toHaveAttribute("data-mode", "rich");
  });
});
