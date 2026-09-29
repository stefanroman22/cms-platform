import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RepeaterEditor } from "../RepeaterEditor";

vi.mock("@/components/dashboard/rich-text/RichTextEditor", () => ({
  RichTextEditor: ({ value, label }: { value: string; label: string }) => {
    const [held] = useState(value); // uncontrolled, like TipTap
    return (
      <div data-testid="rte" aria-label={label}>
        {held}
      </div>
    );
  },
}));

const content = {
  _schema: [{ key: "body", label: "Body", type: "richtext" }],
  items: [{ body: "<p>first</p>" }, { body: "<p>second</p>" }],
};

describe("RepeaterEditor rich fields", () => {
  it("formatted text moves with its item", async () => {
    render(<RepeaterEditor initialContent={content} onChange={() => {}} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    expect(screen.getAllByTestId("rte").map((n) => n.textContent)).toEqual([
      "<p>second</p>",
      "<p>first</p>",
    ]);
  });
  it("removing an item removes its text, not the last one", async () => {
    render(<RepeaterEditor initialContent={content} onChange={() => {}} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Remove item" })[0]);
    expect(screen.getAllByTestId("rte").map((n) => n.textContent)).toEqual(["<p>second</p>"]);
  });
  it("emits items without internal keys", async () => {
    const onChange = vi.fn();
    render(<RepeaterEditor initialContent={content} onChange={onChange} richText />);
    await userEvent.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: content._schema,
      items: [{ body: "<p>second</p>" }, { body: "<p>first</p>" }],
    });
  });
});
