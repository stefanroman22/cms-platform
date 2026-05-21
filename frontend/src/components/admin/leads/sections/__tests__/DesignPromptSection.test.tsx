import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { DesignPromptSection } from "../DesignPromptSection";
import type { Lead } from "../../types";

// Replace TipTap with a simple textarea — tests don't need the real editor.
vi.mock("../DesignPromptEditor", () => ({
  DesignPromptEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      aria-label="Design prompt editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

const lead = { id: "lead-1", design_prompt: "<p>brief</p>" } as unknown as Lead;

describe("DesignPromptSection", () => {
  it("renders read view with stored HTML", () => {
    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getByText("brief")).toBeTruthy();
  });

  it("reveals the editor on pencil click", () => {
    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Design prompt"));
    expect(screen.getByLabelText("Design prompt editor")).toBeTruthy();
  });
});
