import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { LeadsTable } from "./LeadsTable";
import type { Lead } from "./types";

const lead = {
  id: "1",
  business_name: "Acme",
  city: "Berlin",
  category: "cafe",
  web_presence: "none",
  lead_type: "both",
  rating: 4.5,
  review_count: 10,
  lead_status: "not_sent",
  payment_status: "not_applicable",
} as unknown as Lead;

describe("LeadsTable product column", () => {
  it("shows Product header and relabeled lead_type, not Presence", () => {
    render(
      <LeadsTable
        leads={[lead]}
        total={1}
        loading={false}
        page={0}
        pageSize={50}
        onPageChange={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText("Product")).toBeInTheDocument();
    expect(screen.queryByText("Presence")).not.toBeInTheDocument();
    // Both the desktop row and the mobile card render the relabeled product.
    expect(screen.getAllByText("Website + AI Workflow").length).toBeGreaterThan(0);
  });
});
