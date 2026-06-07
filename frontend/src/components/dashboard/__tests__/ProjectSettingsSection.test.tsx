import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ProjectSettingsSection } from "../ProjectSettingsSection";

beforeEach(() => {
  global.fetch = vi.fn((url: string | URL | Request) => {
    const u = typeof url === "string" ? url : url.toString();
    if (u.includes("/locales")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ default_locale: "en", locales: ["en"] }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({
        website_url: "https://example.com",
        allowed_origins: ["https://www.example.com"],
      }),
    });
  }) as unknown as typeof fetch;
});
afterEach(() => vi.restoreAllMocks());

describe("ProjectSettingsSection", () => {
  it("loads and displays the website URL in the form", async () => {
    render(<ProjectSettingsSection projectSlug="demo" />);
    await waitFor(() => {
      expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /save settings/i })).toBeInTheDocument();
  });
});
