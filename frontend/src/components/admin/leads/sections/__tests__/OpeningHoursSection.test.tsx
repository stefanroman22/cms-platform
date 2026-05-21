import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { OpeningHoursSection } from "../OpeningHoursSection";
import type { Lead } from "../../types";

const lead = {
  id: "lead-1",
  opening_hours: { Monday: "9–17" },
} as unknown as Lead;

describe("OpeningHoursSection", () => {
  it("renders 7 day rows in read mode", () => {
    render(
      <EditingSectionProvider>
        <OpeningHoursSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getByText("Monday")).toBeTruthy();
    expect(screen.getByText("Sunday")).toBeTruthy();
    expect(screen.getByText("9–17")).toBeTruthy();
  });

  it("Closed quick-button sets the input to 'Closed'", () => {
    render(
      <EditingSectionProvider>
        <OpeningHoursSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Opening hours"));
    fireEvent.click(screen.getByLabelText("Mark Tuesday closed"));
    const tueInput = screen.getByLabelText("Tuesday hours") as HTMLInputElement;
    expect(tueInput.value).toBe("Closed");
  });
});
