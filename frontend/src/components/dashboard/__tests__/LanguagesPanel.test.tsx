import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguagesPanel } from "../LanguagesPanel";

const GET_RESPONSE = { default_locale: "en", locales: ["en", "nl"] };

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => GET_RESPONSE,
  });
});
afterEach(() => vi.restoreAllMocks());

describe("LanguagesPanel", () => {
  it("renders a chip per locale with the default badged", async () => {
    render(<LanguagesPanel projectSlug="demo" />);

    await waitFor(() => {
      // EN chip
      expect(screen.getByText("en")).toBeInTheDocument();
      // NL chip
      expect(screen.getByText("nl")).toBeInTheDocument();
      // default badge on EN
      expect(screen.getByText("default")).toBeInTheDocument();
    });

    // NL should have a remove button; EN (default) should not
    expect(screen.getByRole("button", { name: /remove nl/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /remove en/i })).not.toBeInTheDocument();
  });

  it("adds a chip when a language is selected and Add is clicked", async () => {
    const user = userEvent.setup();
    render(<LanguagesPanel projectSlug="demo" />);

    // Wait for panel to load
    await waitFor(() => {
      expect(screen.getByText("en")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox", { name: /add a language/i });
    await user.selectOptions(select, "fr"); // French

    const addBtn = screen.getByRole("button", { name: /^add$/i });
    await user.click(addBtn);

    // FR chip should now appear
    expect(screen.getByText("fr")).toBeInTheDocument();
    // Select should be reset
    expect((select as HTMLSelectElement).value).toBe("");
  });

  it("removes a non-default locale chip when × is clicked", async () => {
    const user = userEvent.setup();
    render(<LanguagesPanel projectSlug="demo" />);

    await waitFor(() => {
      expect(screen.getByText("nl")).toBeInTheDocument();
    });

    const removeNl = screen.getByRole("button", { name: /remove nl/i });
    await user.click(removeNl);

    // NL chip should be gone
    expect(screen.queryByText("nl")).not.toBeInTheDocument();
    // EN (default) chip should still be there
    expect(screen.getByText("en")).toBeInTheDocument();
  });

  it("the default locale has no remove button", async () => {
    render(<LanguagesPanel projectSlug="demo" />);

    await waitFor(() => {
      expect(screen.getByText("en")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /remove en/i })).not.toBeInTheDocument();
  });

  it("calls PUT /api/projects/demo/locales with the correct body on save", async () => {
    const putResponse = { default_locale: "en", locales: ["en", "nl"] };
    const fetchMock = vi
      .fn()
      // First call: GET
      .mockResolvedValueOnce({ ok: true, json: async () => GET_RESPONSE })
      // Second call: PUT
      .mockResolvedValueOnce({ ok: true, json: async () => putResponse });
    global.fetch = fetchMock;

    const user = userEvent.setup();
    render(<LanguagesPanel projectSlug="demo" />);

    await waitFor(() => {
      expect(screen.getByText("en")).toBeInTheDocument();
    });

    const saveBtn = screen.getByRole("button", { name: /save languages/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/projects/demo/locales",
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"locales"'),
        })
      );
    });

    // The PUT body should include both locales
    const putCall = fetchMock.mock.calls.find((c) => c[1]?.method === "PUT");
    expect(putCall).toBeDefined();
    const body = JSON.parse(putCall![1].body as string);
    expect(body.locales).toContain("en");
    expect(body.locales).toContain("nl");
    expect(body.default_locale).toBe("en");
  });
});
