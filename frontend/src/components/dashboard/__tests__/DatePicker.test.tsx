import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { DatePicker } from "../DatePicker";

// Pin "now" so the default month + today marker are deterministic.
const NOW = new Date("2026-06-15T09:00:00.000Z");

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});
afterEach(() => vi.useRealTimers());

describe("DatePicker", () => {
  it("shows the placeholder when empty and opens the calendar on click", () => {
    render(<DatePicker value="" onChange={vi.fn()} ariaLabel="Pick date" placeholder="Pick one" />);
    expect(screen.getByText("Pick one")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pick date" }));
    expect(screen.getByRole("dialog", { name: "Pick date" })).toBeInTheDocument();
    // defaults to the current month
    expect(screen.getByText("June 2026")).toBeInTheDocument();
  });

  it("emits the picked day as YYYY-MM-DD and closes", () => {
    const onChange = vi.fn();
    render(<DatePicker value="" onChange={onChange} ariaLabel="Pick date" />);
    fireEvent.click(screen.getByRole("button", { name: "Pick date" }));
    // pick the 20th in the current (June 2026) grid
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("20"));
    expect(onChange).toHaveBeenCalledWith("2026-06-20");
  });

  it("renders a pretty label for a set value", () => {
    render(<DatePicker value="2026-06-20" onChange={vi.fn()} ariaLabel="Pick date" />);
    expect(screen.getByText(/20 Jun 2026/)).toBeInTheDocument();
  });

  it("clears the value when the clear control is used", () => {
    const onChange = vi.fn();
    render(<DatePicker value="2026-06-20" onChange={onChange} clearable ariaLabel="Pick date" />);
    fireEvent.click(screen.getByRole("button", { name: "Clear date" }));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("navigates months without changing the value", () => {
    render(<DatePicker value="" onChange={vi.fn()} ariaLabel="Pick date" />);
    fireEvent.click(screen.getByRole("button", { name: "Pick date" }));
    fireEvent.click(screen.getByRole("button", { name: "Next month" }));
    expect(screen.getByText("July 2026")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
    expect(screen.getByText("June 2026")).toBeInTheDocument();
  });
});
