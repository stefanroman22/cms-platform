import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { TimePicker } from "../TimePicker";

// jsdom doesn't implement scrollIntoView (the picker scrolls the selected slot
// into view on open) — stub it so the component runs.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe("TimePicker", () => {
  it("shows the placeholder when empty and opens the list on click", () => {
    render(<TimePicker value="" onChange={vi.fn()} ariaLabel="Pick time" placeholder="--:--" />);
    expect(screen.getByText("--:--")).toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pick time" }));
    expect(screen.getByRole("listbox", { name: "Pick time" })).toBeInTheDocument();
  });

  it("renders 24h options at the given step and emits the picked time", () => {
    const onChange = vi.fn();
    render(<TimePicker value="09:00" onChange={onChange} step={15} ariaLabel="Pick time" />);
    fireEvent.click(screen.getByRole("button", { name: "Pick time" }));
    const list = screen.getByRole("listbox");
    // 15-min grid → 09:15 exists
    expect(within(list).getByRole("option", { name: "09:15" })).toBeInTheDocument();
    fireEvent.click(within(list).getByRole("option", { name: "13:30" }));
    expect(onChange).toHaveBeenCalledWith("13:30");
  });

  it("marks the current value as the selected option", () => {
    render(<TimePicker value="09:00" onChange={vi.fn()} ariaLabel="Pick time" />);
    fireEvent.click(screen.getByRole("button", { name: "Pick time" }));
    const selected = screen.getByRole("option", { selected: true });
    expect(selected).toHaveTextContent("09:00");
  });

  it("normalizes a backend HH:MM:SS value to HH:MM and selects it", () => {
    // booking_hours times serialize as "HH:MM:SS" — must display + highlight as HH:MM.
    render(<TimePicker value="09:00:00" onChange={vi.fn()} ariaLabel="Pick time" />);
    expect(screen.getByRole("button", { name: "Pick time" })).toHaveTextContent("09:00");
    expect(screen.getByRole("button", { name: "Pick time" })).not.toHaveTextContent("09:00:00");
    fireEvent.click(screen.getByRole("button", { name: "Pick time" }));
    const selected = screen.getByRole("option", { selected: true });
    expect(selected).toHaveTextContent("09:00");
  });

  it("keeps an off-grid value selectable", () => {
    render(<TimePicker value="09:05" onChange={vi.fn()} step={15} ariaLabel="Pick time" />);
    fireEvent.click(screen.getByRole("button", { name: "Pick time" }));
    // 09:05 is not on the 15-min grid but must still appear
    expect(screen.getByRole("option", { name: "09:05" })).toBeInTheDocument();
  });
});
