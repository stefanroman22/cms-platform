import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocaleTabs } from "../LocaleTabs";

describe("LocaleTabs", () => {
  it("renders a tab per locale, marks the active one aria-selected, and badges the default", () => {
    render(
      <LocaleTabs
        locales={["en", "ro", "fr"]}
        activeLocale="ro"
        defaultLocale="en"
        onSelect={vi.fn()}
      />
    );

    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);

    // Uppercased labels
    expect(screen.getByRole("tab", { name: /en/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /ro/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /fr/i })).toBeInTheDocument();

    // Active tab
    expect(screen.getByRole("tab", { name: /ro/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /en/i })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: /fr/i })).toHaveAttribute("aria-selected", "false");

    // Default badge on "en"
    expect(screen.getByText("default")).toBeInTheDocument();
    // Badge is inside the "en" tab button
    const enTab = screen.getByRole("tab", { name: /en/i });
    expect(enTab).toContainElement(screen.getByText("default"));
  });

  it("calls onSelect with the clicked locale", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <LocaleTabs locales={["en", "ro"]} activeLocale="en" defaultLocale="en" onSelect={onSelect} />
    );

    await user.click(screen.getByRole("tab", { name: /ro/i }));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith("ro");
  });

  it("renders nothing when locales.length <= 1", () => {
    const { container } = render(
      <LocaleTabs locales={["en"]} activeLocale="en" defaultLocale="en" onSelect={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("LocaleTabs prefetch", () => {
  it("prefetches a non-active locale on hover and focus, never the active one", () => {
    const onPrefetch = vi.fn();
    render(
      <LocaleTabs
        locales={["nl", "en"]}
        activeLocale="nl"
        defaultLocale="nl"
        onSelect={() => {}}
        onPrefetch={onPrefetch}
      />
    );
    fireEvent.mouseEnter(screen.getByRole("tab", { name: /en/i }));
    fireEvent.focus(screen.getByRole("tab", { name: /en/i }));
    fireEvent.mouseEnter(screen.getByRole("tab", { name: /nl/i }));
    expect(onPrefetch).toHaveBeenCalledWith("en");
    expect(onPrefetch).not.toHaveBeenCalledWith("nl");
  });
});
