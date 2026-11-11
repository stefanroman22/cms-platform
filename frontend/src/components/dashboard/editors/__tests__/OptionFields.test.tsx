import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CmsTheme } from "@/lib/cms-rich-text";
import { OptionFieldInput, type OptionField, type OptionValue } from "../OptionFields";

const themeState = vi.hoisted(() => ({ theme: null as CmsTheme | null }));
vi.mock("@/components/dashboard/theme/ProjectThemeContext", () => ({
  useProjectTheme: () => ({ theme: themeState.theme, serviceKey: null, refresh: () => {} }),
}));
afterEach(() => {
  themeState.theme = null;
});

const THEME: CmsTheme = {
  colors: [
    { name: "Navy", value: "#1e3a8a" },
    { name: "Lemon", value: "#ffeb3b" },
  ],
  surfaces: [{ name: "Page", value: "#ffffff" }],
  fonts: [],
  body_font: "",
  heading_font: "",
};

const TOGGLE: OptionField = { key: "show_title", label: "Show title", type: "toggle" };
const SELECT: OptionField = {
  key: "content_width",
  label: "Content width",
  type: "select",
  options: [
    { value: "narrow", label: "Narrow" },
    { value: "wide", label: "Wide" },
  ],
};
const COLOR: OptionField = { key: "background", label: "Background", type: "color" };

/** Holds the value like a real editor so typed text round-trips. */
function Stateful({
  field,
  initial,
  onChange,
}: {
  field: OptionField;
  initial: unknown;
  onChange: (v: OptionValue) => void;
}) {
  const [value, setValue] = useState<unknown>(initial);
  return (
    <OptionFieldInput
      field={field}
      value={value}
      onChange={(v) => {
        setValue(v);
        onChange(v);
      }}
    />
  );
}

describe("OptionFieldInput toggle", () => {
  it("renders the value and emits a boolean", async () => {
    const onChange = vi.fn();
    render(<OptionFieldInput field={TOGGLE} value={true} onChange={onChange} />);
    const sw = screen.getByRole("switch", { name: "Show title" });
    expect(sw).toHaveAttribute("aria-checked", "true");
    await userEvent.click(sw);
    expect(onChange).toHaveBeenLastCalledWith(false);
  });

  it("is keyboard operable", async () => {
    const onChange = vi.fn();
    render(<OptionFieldInput field={TOGGLE} value={false} onChange={onChange} />);
    screen.getByRole("switch").focus();
    await userEvent.keyboard(" ");
    expect(onChange).toHaveBeenLastCalledWith(true);
  });

  it("shows the default for a missing value without emitting", () => {
    const onChange = vi.fn();
    render(
      <OptionFieldInput
        field={{ ...TOGGLE, default: true }}
        value={undefined}
        onChange={onChange}
      />
    );
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("is off for a missing value without a default", () => {
    render(<OptionFieldInput field={TOGGLE} value={undefined} onChange={() => {}} />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });
});

describe("OptionFieldInput select", () => {
  it("lists only the declared options when a value is chosen", async () => {
    const onChange = vi.fn();
    render(<OptionFieldInput field={SELECT} value="narrow" onChange={onChange} />);
    const select = screen.getByRole("combobox", { name: "Content width" });
    expect(select).toHaveValue("narrow");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Narrow", "Wide"]);
    await userEvent.selectOptions(select, "wide");
    expect(onChange).toHaveBeenLastCalledWith("wide");
  });

  it("offers a Default entry when nothing is chosen", () => {
    render(<OptionFieldInput field={SELECT} value="" onChange={() => {}} />);
    expect(screen.getByRole("combobox")).toHaveValue("");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Default",
      "Narrow",
      "Wide",
    ]);
  });

  it("treats an unknown value as not chosen", () => {
    render(<OptionFieldInput field={SELECT} value="huge" onChange={() => {}} />);
    expect(screen.getByRole("combobox")).toHaveValue("");
    expect(screen.getByRole("option", { name: "Default" })).toBeInTheDocument();
  });

  it("shows the default for a missing value without emitting", () => {
    const onChange = vi.fn();
    render(
      <OptionFieldInput
        field={{ ...SELECT, default: "wide" }}
        value={undefined}
        onChange={onChange}
      />
    );
    expect(screen.getByRole("combobox")).toHaveValue("wide");
    expect(screen.queryByRole("option", { name: "Default" })).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("OptionFieldInput color", () => {
  it("shows Default and no swatches for an empty value without a theme", () => {
    render(<OptionFieldInput field={COLOR} value="" onChange={() => {}} />);
    const group = screen.getByRole("group", { name: "Background" });
    expect(group).toHaveTextContent("Default");
    expect(screen.getByLabelText("Background hex")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Clear" })).toBeDisabled();
    expect(within(group).getAllByRole("button")).toHaveLength(1); // Clear only, no swatches
  });

  it("commits a typed hex only when valid, normalised to lowercase #rrggbb", async () => {
    const onChange = vi.fn();
    render(<Stateful field={COLOR} initial="" onChange={onChange} />);
    const hex = screen.getByLabelText("Background hex");
    await userEvent.type(hex, "#1G");
    expect(onChange).not.toHaveBeenCalled();
    await userEvent.clear(hex);
    await userEvent.type(hex, "#ABC");
    expect(onChange).toHaveBeenLastCalledWith("#aabbcc");
    expect(hex).toHaveValue("#ABC");
    await userEvent.tab();
    expect(hex).toHaveValue("#aabbcc");
  });

  it("reverts an invalid hex on blur", async () => {
    const onChange = vi.fn();
    render(<Stateful field={COLOR} initial="#112233" onChange={onChange} />);
    const hex = screen.getByLabelText("Background hex");
    await userEvent.clear(hex);
    await userEvent.type(hex, "#12");
    await userEvent.tab();
    expect(hex).toHaveValue("#112233");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("picks from the native colour input", () => {
    const onChange = vi.fn();
    render(<OptionFieldInput field={COLOR} value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Pick Background colour"), {
      target: { value: "#000000" },
    });
    expect(onChange).toHaveBeenLastCalledWith("#000000");
  });

  it("offers the theme's colours and surfaces as swatches", async () => {
    themeState.theme = THEME;
    const onChange = vi.fn();
    render(<OptionFieldInput field={COLOR} value="#1e3a8a" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Navy" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Page" })).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(screen.getByRole("button", { name: "Lemon" }));
    expect(onChange).toHaveBeenLastCalledWith("#ffeb3b");
  });

  it("clears to an empty string", async () => {
    const onChange = vi.fn();
    render(<OptionFieldInput field={COLOR} value="#112233" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onChange).toHaveBeenLastCalledWith("");
  });

  it("shows the default for a missing value without emitting", () => {
    const onChange = vi.fn();
    render(
      <OptionFieldInput
        field={{ ...COLOR, default: "#ABC" }}
        value={undefined}
        onChange={onChange}
      />
    );
    expect(screen.getByLabelText("Background hex")).toHaveValue("#aabbcc");
    expect(onChange).not.toHaveBeenCalled();
  });
});
