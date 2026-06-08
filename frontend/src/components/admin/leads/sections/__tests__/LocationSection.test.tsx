import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { LocationSection } from "../LocationSection";
import type { Lead } from "../../types";

const baseLead = {
  id: "lead-1",
  address: "Main 1",
  city: "Lelystad",
  country: "NL",
  postal_code: "8232",
  lat: 52.5,
  lng: 5.5,
} as unknown as Lead;

describe("LocationSection", () => {
  it("renders address read row", () => {
    render(
      <EditingSectionProvider>
        <LocationSection lead={baseLead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getByText("Main 1")).toBeTruthy();
  });

  it("flags lat/lng error when only one is set", () => {
    render(
      <EditingSectionProvider>
        <LocationSection lead={baseLead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Location"));
    const lng = screen.getByLabelText("Longitude") as HTMLInputElement;
    fireEvent.change(lng, { target: { value: "" } });
    expect(screen.getByText(/both latitude and longitude/i)).toBeTruthy();
  });
});
