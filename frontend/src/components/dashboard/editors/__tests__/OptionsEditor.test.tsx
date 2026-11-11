import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OptionsEditor } from "../OptionsEditor";

vi.mock("@/components/dashboard/theme/ProjectThemeContext", () => ({
  useProjectTheme: () => ({ theme: null, serviceKey: null, refresh: () => {} }),
}));

const schema = [
  { key: "show_title", label: "Show title", type: "toggle", default: true },
  {
    key: "content_width",
    label: "Content width",
    type: "select",
    options: [
      { value: "narrow", label: "Narrow" },
      { value: "wide", label: "Wide" },
    ],
    default: "wide",
  },
  { key: "background", label: "Background", type: "color" },
];

describe("OptionsEditor", () => {
  it("lists every field with its control and no type tags", () => {
    render(
      <OptionsEditor
        initialContent={{ _schema: schema, values: { show_title: false } }}
        onChange={() => {}}
      />
    );
    expect(screen.getByRole("switch", { name: "Show title" })).toHaveAttribute(
      "aria-checked",
      "false"
    );
    expect(screen.getByRole("combobox", { name: "Content width" })).toHaveValue("wide");
    expect(screen.getByRole("group", { name: "Background" })).toBeInTheDocument();
    expect(screen.queryByText(/\((toggle|select|color)\)/)).toBeNull();
    expect(screen.queryByRole("button", { name: /add|remove|move/i })).toBeNull();
  });

  it("emits { _schema, values } with the full values object", async () => {
    const onChange = vi.fn();
    render(<OptionsEditor initialContent={{ _schema: schema, values: {} }} onChange={onChange} />);
    expect(onChange).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("switch", { name: "Show title" }));
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: schema,
      values: { show_title: false, content_width: "wide", background: "" },
    });
    await userEvent.selectOptions(screen.getByRole("combobox"), "narrow");
    expect(onChange).toHaveBeenLastCalledWith({
      _schema: schema,
      values: { show_title: false, content_width: "narrow", background: "" },
    });
  });

  it.each([{}, { _schema: [] }, { _schema: "nope", values: {} }])(
    "shows a notice when no field schema is defined (%o)",
    (content) => {
      render(<OptionsEditor initialContent={content} onChange={() => {}} />);
      expect(screen.getByText(/no field schema defined/i)).toBeInTheDocument();
    }
  );
});
