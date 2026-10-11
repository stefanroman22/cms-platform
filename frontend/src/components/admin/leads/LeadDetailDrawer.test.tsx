import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LeadDetailDrawer } from "./LeadDetailDrawer";
import type { Lead } from "./types";

const base = {
  id: "lead-1",
  business_name: "Acme",
  category: "Barber",
  source_url: null,
  lead_status: "not_sent",
  website_build_status: "not_started",
  ai_workflow_status: "not_started",
  lead_contact_type: "not_contacted",
  payment_status: "not_applicable",
  call_count: 0,
  notes: null,
  closed_amount: null,
  closed_at: null,
  photo_urls: [],
  extra: {},
  languages: [],
  reviews: null,
  opening_hours: null,
  social_links: {},
  types: [],
  google_place_id: "ChIJx",
} as unknown as Lead;

describe("LeadDetailDrawer re-import", () => {
  it("re-imports with the stored place id and overwrite flag", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...base, business_name: "Fresh" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const onPatched = vi.fn();
    render(
      <LeadDetailDrawer lead={base} onClose={vi.fn()} onPatched={onPatched} onDeleted={vi.fn()} />
    );
    fireEvent.click(screen.getByRole("button", { name: /re-import/i }));
    expect(screen.queryByLabelText("Google Maps link or place ID")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Overwrite existing fields"));
    fireEvent.click(screen.getByRole("button", { name: /import from google/i }));
    await waitFor(() =>
      expect(onPatched).toHaveBeenCalledWith(expect.objectContaining({ business_name: "Fresh" }))
    );
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/leads/lead-1/google-import");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ overwrite: true });
    vi.unstubAllGlobals();
  });

  it("shows an error when a 200 response is not a lead", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const onPatched = vi.fn();
    render(
      <LeadDetailDrawer lead={base} onClose={vi.fn()} onPatched={onPatched} onDeleted={vi.fn()} />
    );
    fireEvent.click(screen.getByRole("button", { name: /re-import/i }));
    fireEvent.click(screen.getByRole("button", { name: /import from google/i }));
    expect(await screen.findByText("Unexpected response from the server")).toBeInTheDocument();
    expect(onPatched).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("asks for a link when the lead has no place id and shows candidates", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        status: "candidates",
        candidates: [{ place_id: "ChIJ1", name: "Acme Barber", address: "Main 1" }],
        warnings: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <LeadDetailDrawer
        lead={{ ...base, google_place_id: null } as Lead}
        onClose={vi.fn()}
        onPatched={vi.fn()}
        onDeleted={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /re-import/i }));
    fireEvent.change(screen.getByLabelText("Google Maps link or place ID"), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: /import from google/i }));
    expect(await screen.findByRole("button", { name: /acme barber/i })).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      input: "Acme",
      overwrite: false,
    });
    vi.unstubAllGlobals();
  });
});
