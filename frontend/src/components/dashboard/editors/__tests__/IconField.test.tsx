import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CmsIconValue, CmsTheme } from "@/lib/cms-rich-text";
import { IconField } from "../IconField";

const themeState = vi.hoisted(() => ({ theme: null as CmsTheme | null }));
vi.mock("@/components/dashboard/theme/ProjectThemeContext", () => ({
  useProjectTheme: () => ({ theme: themeState.theme, serviceKey: null, refresh: () => {} }),
}));
afterEach(() => {
  themeState.theme = null;
});

vi.mock("lucide-react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("lucide-react")>();
  const Wrench = () => (
    <svg viewBox="0 0 24 24">
      <path d="M1 1h22" />
    </svg>
  );
  const Hammer = () => (
    <svg viewBox="0 0 24 24">
      <path d="M2 2h20" />
    </svg>
  );
  const Building2 = () => (
    <svg viewBox="0 0 24 24">
      <path d="M3 3h18" />
    </svg>
  );
  const Grid3x3 = () => (
    <svg viewBox="0 0 24 24">
      <path d="M4 4h16" />
    </svg>
  );
  return { ...actual, icons: { Wrench, Hammer, Building2, Grid3x3 } };
});

// The picker and the lucide icon set load lazily; allow slow chunks under machine load.
const LAZY = { timeout: 10000 };

const THEME: CmsTheme = {
  colors: [
    { name: "Navy", value: "#1e3a8a" },
    { name: "Lemon", value: "#ffeb3b" },
  ],
  surfaces: [
    { name: "Page", value: "#ffffff" },
    { name: "Footer", value: "#111111" },
  ],
  fonts: [],
  body_font: "",
  heading_font: "",
};

const SVG_ICON: CmsIconValue = {
  src: "https://cdn.example.com/icons/star.svg",
  mode: "tint",
  color: "",
  name: "star",
};

describe("IconField", () => {
  it("marks only the swatches that contrast with the field's surface", () => {
    themeState.theme = THEME;
    render(<IconField value={SVG_ICON} onChange={() => {}} surface="Page" />);
    const navy = screen.getByRole("button", { name: /Navy/ });
    const lemon = screen.getByRole("button", { name: /Lemon/ });
    expect(within(navy).getByText("✓")).toBeInTheDocument();
    expect(within(lemon).queryByText("✓")).toBeNull();
    expect(within(lemon).getByText("low contrast")).toBeInTheDocument();
  });

  it("offers only site default and a custom colour without a theme", () => {
    render(<IconField value={SVG_ICON} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Site default" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByLabelText("Custom colour")).toBeInTheDocument();
    expect(screen.queryByText("low contrast")).toBeNull();
  });

  it("picking a swatch sets the icon colour", async () => {
    themeState.theme = THEME;
    const onChange = vi.fn();
    render(<IconField value={SVG_ICON} onChange={onChange} surface="Page" />);
    await userEvent.click(screen.getByRole("button", { name: /Navy/ }));
    expect(onChange).toHaveBeenLastCalledWith({ ...SVG_ICON, color: "#1e3a8a" });
  });

  it("uploading a PNG forces original colours", async () => {
    const onChange = vi.fn();
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example.com/icons/logo.png");
    const { container } = render(
      <IconField value={SVG_ICON} onChange={onChange} onUpload={onUpload} />
    );
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    expect(input).toHaveAttribute("accept", "image/svg+xml,image/png,image/webp");
    await userEvent.upload(input, new File(["x"], "logo.png", { type: "image/png" }));
    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith({
        src: "https://cdn.example.com/icons/logo.png",
        mode: "original",
        color: "",
        name: "logo.png",
      })
    );
  });

  it("disables recolouring for a non-SVG icon", () => {
    render(
      <IconField
        value={{ ...SVG_ICON, src: "https://cdn.example.com/icons/logo.png", mode: "original" }}
        onChange={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: "Recolour" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Original colours" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.queryByRole("button", { name: "Site default" })).toBeNull();
  });

  it("switches an SVG icon to original colours", async () => {
    const onChange = vi.fn();
    render(<IconField value={SVG_ICON} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Original colours" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...SVG_ICON, mode: "original" });
  });

  it("removes the icon", async () => {
    const onChange = vi.fn();
    render(<IconField value={SVG_ICON} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("picking a library icon uploads it as SVG and emits a lucide name", async () => {
    const onChange = vi.fn();
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example.com/icons/wrench.svg");
    render(
      <IconField
        value={{ ...SVG_ICON, color: "#1e3a8a" }}
        onChange={onChange}
        onUpload={onUpload}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Choose icon" }));
    await userEvent.type(
      await screen.findByRole("searchbox", { name: "Search icons" }, LAZY),
      "wre"
    );
    expect(screen.queryByRole("button", { name: "Hammer" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Wrench" }));

    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith({
        src: "https://cdn.example.com/icons/wrench.svg",
        mode: "tint",
        color: "#1e3a8a",
        name: "lucide:wrench",
      })
    );
    const file = onUpload.mock.calls[0][0] as File;
    expect(file.type).toBe("image/svg+xml");
    expect(file.name).toBe("wrench.svg");
    const text = await file.text();
    expect(text).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(text).toContain('<path d="M1 1h22"');
  }, 20000);

  it.each([
    ["Building2", "building-2"],
    ["Grid3x3", "grid-3x3"],
  ])(
    "names library icon %s like Lucide (%s)",
    async (icon, slug) => {
      const onChange = vi.fn();
      const onUpload = vi.fn().mockResolvedValue(`https://cdn.example.com/icons/${slug}.svg`);
      render(<IconField value={SVG_ICON} onChange={onChange} onUpload={onUpload} />);
      await userEvent.click(screen.getByRole("button", { name: "Choose icon" }));
      await userEvent.click(await screen.findByRole("button", { name: icon }, LAZY));
      await waitFor(() =>
        expect(onChange).toHaveBeenLastCalledWith(
          expect.objectContaining({ name: `lucide:${slug}` })
        )
      );
      expect((onUpload.mock.calls[0][0] as File).name).toBe(`${slug}.svg`);
    },
    20000
  );

  it("returns focus to Choose icon after picking an icon", async () => {
    const onUpload = vi.fn().mockResolvedValue("https://cdn.example.com/icons/wrench.svg");
    render(<IconField value={SVG_ICON} onChange={() => {}} onUpload={onUpload} />);
    const choose = screen.getByRole("button", { name: "Choose icon" });
    await userEvent.click(choose);
    await userEvent.click(await screen.findByRole("button", { name: "Wrench" }, LAZY));
    await waitFor(() => expect(onUpload).toHaveBeenCalled());
    await waitFor(() => expect(choose).toHaveFocus());
  }, 20000);

  it("can pick black as a custom colour from the Site default state", () => {
    const onChange = vi.fn();
    render(<IconField value={SVG_ICON} onChange={onChange} />);
    const custom = screen.getByLabelText("Custom colour");
    expect(custom).not.toHaveValue("#000000");
    fireEvent.change(custom, { target: { value: "#000000" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...SVG_ICON, color: "#000000" });
  });
});
