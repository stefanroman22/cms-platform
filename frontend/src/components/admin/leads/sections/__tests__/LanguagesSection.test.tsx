import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { LanguagesSection } from "../LanguagesSection";
import type { Lead } from "../../types";

function makeLead(languages: string[]): Lead {
  return { id: "lead-1", languages } as unknown as Lead;
}

function renderSection(lead: Lead) {
  return render(
    <EditingSectionProvider>
      <LanguagesSection lead={lead} onPatched={vi.fn()} />
    </EditingSectionProvider>
  );
}

describe("LanguagesSection", () => {
  it("renders existing languages as chips in read view", () => {
    renderSection(makeLead(["Romanian", "Dutch"]));
    expect(screen.getByText("Romanian")).toBeTruthy();
    expect(screen.getByText("Dutch")).toBeTruthy();
  });

  it("shows an empty state when there are no languages", () => {
    renderSection(makeLead([]));
    expect(screen.getByText(/no languages/i)).toBeTruthy();
  });

  it("adds a language via search in edit view", () => {
    renderSection(makeLead([]));
    fireEvent.click(screen.getByLabelText("Edit Languages"));
    const input = screen.getByLabelText("Search languages");
    fireEvent.change(input, { target: { value: "roman" } });
    fireEvent.mouseDown(screen.getByText("Romanian"));
    expect(screen.getByLabelText("Remove Romanian")).toBeTruthy();
  });

  it("removes a language via the chip × button in edit view", () => {
    renderSection(makeLead(["Romanian"]));
    fireEvent.click(screen.getByLabelText("Edit Languages"));
    fireEvent.click(screen.getByLabelText("Remove Romanian"));
    expect(screen.queryByLabelText("Remove Romanian")).toBeNull();
  });

  it("adds the highlighted match on Enter", () => {
    renderSection(makeLead([]));
    fireEvent.click(screen.getByLabelText("Edit Languages"));
    const input = screen.getByLabelText("Search languages");
    fireEvent.change(input, { target: { value: "dutch" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByLabelText("Remove Dutch")).toBeTruthy();
  });

  it("removes the last chip on Backspace when the search is empty", () => {
    renderSection(makeLead(["Romanian", "Dutch"]));
    fireEvent.click(screen.getByLabelText("Edit Languages"));
    const input = screen.getByLabelText("Search languages");
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(screen.queryByLabelText("Remove Dutch")).toBeNull();
    expect(screen.getByLabelText("Remove Romanian")).toBeTruthy();
  });
});
