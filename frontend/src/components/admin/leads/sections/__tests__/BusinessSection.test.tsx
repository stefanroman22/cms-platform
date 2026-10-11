import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BusinessSection } from "../BusinessSection";
import type { Lead } from "../../types";

describe("BusinessSection", () => {
  it("renders Google business facts", () => {
    const lead = {
      business_status: "CLOSED_TEMPORARILY",
      primary_type: "barber_shop",
      price_level: "moderate",
      types: ["barber_shop", "hair_salon"],
      google_imported_at: "2026-10-11T10:00:00Z",
      extra: {
        google: {
          generative_summary: { overview: "Sharp fades.", disclosure: "Summarized with Gemini" },
        },
      },
    } as unknown as Lead;
    render(<BusinessSection lead={lead} />);
    expect(screen.getByText("Closed temporarily")).toBeInTheDocument();
    expect(screen.getByText("Barber shop")).toBeInTheDocument();
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(screen.getByText("hair salon")).toBeInTheDocument();
    expect(screen.getByText("Sharp fades.")).toBeInTheDocument();
    expect(screen.getByText(/Summarized with Gemini/)).toBeInTheDocument();
  });

  it("lists the last import notes", () => {
    const lead = {
      google_place_id: "ChIJx",
      types: [],
      google_imported_at: "2026-10-11T10:00:00Z",
      extra: {
        google: {
          import_warnings: ["website enrichment skipped: OSError: refused", "photo 2 skipped"],
        },
      },
    } as unknown as Lead;
    render(<BusinessSection lead={lead} />);
    expect(screen.getByText("Last import notes")).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      "website enrichment skipped: OSError: refused",
      "photo 2 skipped",
    ]);
  });

  it("hides Google types when only generic types remain", () => {
    const lead = {
      google_place_id: "ChIJx",
      primary_type: "barber_shop",
      types: ["barber_shop", "point_of_interest", "establishment"],
      extra: {},
    } as unknown as Lead;
    render(<BusinessSection lead={lead} />);
    expect(screen.queryByText("Google types")).not.toBeInTheDocument();
    expect(screen.queryByText("Last import notes")).not.toBeInTheDocument();
  });

  it("renders nothing when the lead was never imported", () => {
    const { container } = render(
      <BusinessSection lead={{ google_place_id: null, extra: {} } as unknown as Lead} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
