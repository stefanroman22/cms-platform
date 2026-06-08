import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SectionPanel } from "../SectionPanel";

describe("SectionPanel", () => {
  it("renders its children inside a tabpanel labelled by the active tab", () => {
    render(
      <SectionPanel activeView="cms">
        <p>CMS body</p>
      </SectionPanel>
    );
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", "section-tab-cms");
    expect(screen.getByText("CMS body")).toBeInTheDocument();
  });
});
