import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { AboutSection } from "../AboutSection";
import type { Lead } from "../../types";

const lead = {
  id: "lead-1",
  extra: {
    attributes: {
      "Service options": { "Dine-in": true, Takeout: false },
    },
  },
} as unknown as Lead;

describe("AboutSection", () => {
  it("renders existing attributes in read view", () => {
    render(
      <EditingSectionProvider>
        <AboutSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getByText("Service options")).toBeTruthy();
    expect(screen.getByText("Dine-in")).toBeTruthy();
  });

  it("toggles an attribute in edit mode", () => {
    render(
      <EditingSectionProvider>
        <AboutSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit About this business"));
    const toggle = screen.getByLabelText("Toggle Dine-in") as HTMLButtonElement;
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
  });

  it("adds a new attribute when the user types and submits", () => {
    render(
      <EditingSectionProvider>
        <AboutSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit About this business"));
    const addInput = screen.getByPlaceholderText(
      /new attribute in Service options/i
    ) as HTMLInputElement;
    fireEvent.change(addInput, { target: { value: "Delivery" } });
    fireEvent.keyDown(addInput, { key: "Enter" });
    expect(screen.getByText("Delivery")).toBeTruthy();
  });
});
