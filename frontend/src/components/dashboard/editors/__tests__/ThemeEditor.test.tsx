import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeEditor } from "../ThemeEditor";

const initial = {
  colors: [{ name: "Brand", value: "#1e5aa8" }],
  surfaces: [{ name: "Page", value: "#ffffff" }],
  fonts: [{ family: "Inter", source: "google", weights: [400, 700], italic: false }],
  body_font: "",
  heading_font: "",
};

const OPEN_SANS = "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
});
afterEach(() => vi.restoreAllMocks());

function lastEmit(onChange: ReturnType<typeof vi.fn>) {
  return onChange.mock.calls[onChange.mock.calls.length - 1][0];
}

async function addGoogleFont(family: string) {
  const user = userEvent.setup();
  await user.type(screen.getByRole("combobox", { name: "Google font family" }), family);
  await user.click(screen.getByRole("button", { name: "Add Google font" }));
}

describe("ThemeEditor", () => {
  it("renders the initial fonts, colours and surfaces", () => {
    render(<ThemeEditor initialContent={initial} onChange={() => {}} />);
    expect(screen.getByText("Inter", { selector: "span" })).toBeInTheDocument();
    expect(screen.getAllByText("The quick brown fox · Aa Ăă Șș Țț")).toHaveLength(1);
    expect(screen.getByDisplayValue("Brand")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Colour 1 hex" })).toHaveValue("#1e5aa8");
    expect(screen.getByDisplayValue("Page")).toBeInTheDocument();
  });

  it("adding a catalog font probes its css2 URL and emits weights 400+700", async () => {
    const onChange = vi.fn();
    render(<ThemeEditor initialContent={initial} onChange={onChange} />);
    await addGoogleFont("Open Sans");
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith(OPEN_SANS, { mode: "cors" });
    expect(lastEmit(onChange).fonts).toEqual([
      initial.fonts[0],
      { family: "Open Sans", source: "google", weights: [400, 700], italic: false },
    ]);
  });

  it("falls back to weight 400, then to no weights, when Google rejects the request", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({ ok: true });
    const onChange = vi.fn();
    render(<ThemeEditor initialContent={initial} onChange={onChange} />);
    await addGoogleFont("Open Sans");
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const urls = vi.mocked(global.fetch).mock.calls.map((c) => c[0]);
    expect(urls).toEqual([
      OPEN_SANS,
      "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400&display=swap",
      "https://fonts.googleapis.com/css2?family=Open+Sans&display=swap",
    ]);
    expect(lastEmit(onChange).fonts[1]).toMatchObject({ family: "Open Sans", weights: [] });
  });

  it("reports a family Google Fonts does not have", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    const onChange = vi.fn();
    render(<ThemeEditor initialContent={initial} onChange={onChange} />);
    await addGoogleFont("Nope Font");
    expect(await screen.findByText("Google Fonts has no family called Nope Font")).toBeVisible();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not emit an invalid hex typed into a colour row", () => {
    const onChange = vi.fn();
    render(<ThemeEditor initialContent={initial} onChange={onChange} />);
    const hex = screen.getByRole("textbox", { name: "Colour 1 hex" });
    fireEvent.change(hex, { target: { value: "#12zz" } });
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(hex, { target: { value: "#ABC" } });
    expect(lastEmit(onChange).colors).toEqual([{ name: "Brand", value: "#aabbcc" }]);
  });

  it("choosing a body font emits body_font", async () => {
    const onChange = vi.fn();
    render(<ThemeEditor initialContent={initial} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText("Body font"), "Inter");
    expect(lastEmit(onChange)).toEqual({ ...initial, body_font: "Inter" });
  });

  it("uploads a font file and emits an upload font", async () => {
    const onChange = vi.fn();
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example/acme/brand.woff2");
    render(<ThemeEditor initialContent={initial} onChange={onChange} onUpload={onUpload} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Uploaded font family"), "Brand Sans");
    const file = new File(["x"], "brand.woff2", { type: "font/woff2" });
    await user.upload(screen.getByLabelText("Font file"), file);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(onUpload).toHaveBeenCalledWith(file);
    expect(lastEmit(onChange).fonts[1]).toEqual({
      family: "Brand Sans",
      source: "upload",
      files: [{ url: "https://cdn.example/acme/brand.woff2", weight: 400, style: "normal" }],
    });
  });

  it("resets the file input after a failed family check so the same file can be chosen again", async () => {
    const onChange = vi.fn();
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example/acme/brand.woff2");
    render(<ThemeEditor initialContent={initial} onChange={onChange} onUpload={onUpload} />);
    const user = userEvent.setup();
    const input = screen.getByLabelText("Font file") as HTMLInputElement;
    const file = new File(["x"], "brand.woff2", { type: "font/woff2" });
    await user.upload(input, file);
    expect(onUpload).not.toHaveBeenCalled();
    expect(input.value).toBe("");
    await user.type(screen.getByLabelText("Uploaded font family"), "Brand Sans");
    await user.upload(input, file);
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith(file));
  });

  it("removing the body font clears body_font", async () => {
    const onChange = vi.fn();
    render(<ThemeEditor initialContent={{ ...initial, body_font: "Inter" }} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove Inter" }));
    expect(lastEmit(onChange)).toMatchObject({ fonts: [], body_font: "" });
  });
});
