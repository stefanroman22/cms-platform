import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ImageEditor } from "../ImageEditor";
import { ImageHint } from "../ImageHint";

// jsdom decodes no images: report a fixed natural size on load.
const natural = vi.hoisted(() => ({ width: 1000, height: 1000 }));
class FakeImage {
  naturalWidth = 0;
  naturalHeight = 0;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  set src(_v: string) {
    this.naturalWidth = natural.width;
    this.naturalHeight = natural.height;
    queueMicrotask(() => this.onload?.());
  }
}

beforeEach(() => {
  vi.stubGlobal("Image", FakeImage);
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

describe("ImageHint", () => {
  it("states the recommended size, orientation and reduced ratio", () => {
    render(<ImageHint hint={{ width: 1600, height: 600 }} />);
    expect(
      screen.getByText("Recommended: 1600 × 600 px (landscape 8:3) · JPG or WebP · under 500 KB")
    ).toBeInTheDocument();
  });

  it("falls back to a decimal ratio when the reduced terms are large", () => {
    render(<ImageHint hint={{ width: 1601, height: 600 }} />);
    expect(screen.getByText(/\(landscape 2\.67:1\)/)).toBeInTheDocument();
  });

  it("names portrait and square slots", () => {
    const { rerender } = render(<ImageHint hint={{ width: 600, height: 900 }} />);
    expect(screen.getByText(/\(portrait 2:3\)/)).toBeInTheDocument();
    rerender(<ImageHint hint={{ width: 800, height: 800 }} />);
    expect(screen.getByText(/\(square 1:1\)/)).toBeInTheDocument();
  });

  it("gives general advice without a hint", () => {
    render(<ImageHint />);
    expect(
      screen.getByText(
        "Recommended: JPG, WebP or PNG, at least 1200 px wide, under 500 KB. SVG for logos and illustrations."
      )
    ).toBeInTheDocument();
  });

  it("warns about cropping, blur and file size", () => {
    render(
      <ImageHint
        hint={{ width: 1600, height: 600 }}
        measured={{ width: 500, height: 500 }}
        bytes={2 * 1024 * 1024}
      />
    );
    expect(
      screen.getByText("This image is 1:1 but the slot is 8:3; it will be cropped.")
    ).toBeInTheDocument();
    expect(screen.getByText("Smaller than recommended; it may look blurry.")).toBeInTheDocument();
    expect(screen.getByText("Large file; compress it to keep the site fast.")).toBeInTheDocument();
  });

  it("does not warn for a matching image", () => {
    render(
      <ImageHint
        hint={{ width: 1600, height: 600 }}
        measured={{ width: 1600, height: 620 }}
        bytes={300_000}
      />
    );
    expect(screen.queryByText(/cropped|blurry|Large file/)).toBeNull();
  });
});

describe("ImageEditor", () => {
  const hint = { width: 1600, height: 600 };

  it("shows the size hint from _hint", () => {
    render(<ImageEditor initialContent={{ url: "", alt: "", _hint: hint }} onChange={() => {}} />);
    expect(screen.getByText(/1600 × 600 px \(landscape 8:3\)/)).toBeInTheDocument();
  });

  it("measures the upload, warns about the aspect and keeps _hint unchanged", async () => {
    const onChange = vi.fn();
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example.com/a.png");
    const { container } = render(
      <ImageEditor
        initialContent={{ url: "", alt: "Hero", _hint: hint }}
        onChange={onChange}
        onUpload={onUpload}
      />
    );
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent.upload(input, new File(["x"], "a.png", { type: "image/png" }));
    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith({
        url: "https://cdn.example.com/a.png",
        alt: "Hero",
        _hint: hint,
      })
    );
    expect(
      await screen.findByText("This image is 1:1 but the slot is 8:3; it will be cropped.")
    ).toBeInTheDocument();
  });

  it("emits no _hint when the content has none", async () => {
    const onChange = vi.fn();
    render(<ImageEditor initialContent={{ url: "", alt: "" }} onChange={onChange} />);
    await userEvent.type(screen.getByPlaceholderText(/Describe the image/), "A");
    expect(onChange).toHaveBeenLastCalledWith({ url: "", alt: "A" });
  });
});
