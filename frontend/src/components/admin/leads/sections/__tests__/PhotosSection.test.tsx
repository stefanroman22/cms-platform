import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { PhotosSection } from "../PhotosSection";
import type { Lead } from "../../types";

const A = "https://x.supabase.co/storage/v1/object/public/lead-photos/l/00-a.jpg";
const B = "https://x.supabase.co/storage/v1/object/public/lead-photos/l/01-b.jpg";
const lead = {
  id: "lead-1",
  photo_urls: [A, B],
  extra: {
    google: {
      photos: [
        {
          url: A,
          owner_photo: true,
          attributions: [{ name: "Samir Kapsalon", uri: "https://g/c/1" }],
          google_maps_uri: "https://g/p/a",
        },
        {
          url: B,
          owner_photo: false,
          attributions: [{ name: "Jan", uri: null }],
          google_maps_uri: "https://g/p/b",
        },
      ],
    },
  },
} as unknown as Lead;

describe("PhotosSection", () => {
  it("renders photos with attribution and owner badge", () => {
    render(
      <EditingSectionProvider>
        <PhotosSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getAllByRole("img")).toHaveLength(2);
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText(/Samir Kapsalon/)).toBeInTheDocument();
    expect(screen.getByText("Jan").closest("a")).toHaveAttribute("href", "https://g/p/b");
  });

  it("shows an empty state", () => {
    render(
      <EditingSectionProvider>
        <PhotosSection lead={{ ...lead, photo_urls: [] } as Lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    expect(screen.getByText(/no photos/i)).toBeInTheDocument();
  });

  it("removing a photo PATCHes the remaining list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ ...lead, photo_urls: [B] }) });
    vi.stubGlobal("fetch", fetchMock);
    const onPatched = vi.fn();
    render(
      <EditingSectionProvider>
        <PhotosSection lead={lead} onPatched={onPatched} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getAllByRole("button", { name: /remove photo/i })[0]);
    await waitFor(() => expect(onPatched).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ photo_urls: [B] });
    vi.unstubAllGlobals();
  });
});
