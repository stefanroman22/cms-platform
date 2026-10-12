import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import * as cache from "@/lib/cache";
import { ProjectThemeProvider, useProjectTheme } from "../ProjectThemeContext";

const THEME = {
  colors: [{ name: "Brand", value: "#1e5aa8" }],
  surfaces: [],
  fonts: [{ family: "Inter", source: "google", weights: [400], italic: false }],
  body_font: "Inter",
  heading_font: "",
};

function Probe() {
  const ctx = useProjectTheme();
  return (
    <>
      <p data-testid="probe">
        {ctx.serviceKey ?? "none"}:{ctx.theme?.body_font ?? "no theme"}:{ctx.theme?.colors.length}
      </p>
      <button onClick={ctx.refresh}>Refresh</button>
    </>
  );
}

beforeEach(() => {
  cache.clearAll();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ theme: THEME, service_key: "general_theme" }),
  });
});
afterEach(() => vi.restoreAllMocks());

describe("ProjectThemeProvider", () => {
  it("fetches the project theme and exposes it", async () => {
    render(
      <ProjectThemeProvider projectSlug="acme">
        <Probe />
      </ProjectThemeProvider>
    );
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent("general_theme:Inter:1")
    );
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/projects/acme/theme",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("exposes a null theme when the project has none", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ theme: null, service_key: null }),
    });
    render(
      <ProjectThemeProvider projectSlug="acme">
        <Probe />
      </ProjectThemeProvider>
    );
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("none:no theme:"));
  });

  it("refresh refetches the theme", async () => {
    render(
      <ProjectThemeProvider projectSlug="acme">
        <Probe />
      </ProjectThemeProvider>
    );
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("general_theme"));
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        theme: { ...THEME, colors: [...THEME.colors, { name: "Accent", value: "#ff0000" }] },
        service_key: "general_theme",
      }),
    });
    act(() => screen.getByRole("button", { name: "Refresh" }).click());
    await waitFor(() =>
      expect(screen.getByTestId("probe")).toHaveTextContent("general_theme:Inter:2")
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("loads the theme's Google fonts", async () => {
    render(
      <ProjectThemeProvider projectSlug="acme">
        <Probe />
      </ProjectThemeProvider>
    );
    await waitFor(() =>
      expect(document.querySelector('link[rel="stylesheet"]')?.getAttribute("href")).toBe(
        "https://fonts.googleapis.com/css2?family=Inter:wght@400&display=swap"
      )
    );
  });
});
