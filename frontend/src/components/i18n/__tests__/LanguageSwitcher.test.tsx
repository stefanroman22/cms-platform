import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageSwitcher } from "../LanguageSwitcher";

const replace = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  usePathname: () => "/about",
  useRouter: () => ({ replace }),
}));
vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: () => (key: string) => key,
}));

beforeEach(() => replace.mockClear());

describe("LanguageSwitcher (nav)", () => {
  it("opens the menu and lists the three native names", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher variant="nav" />);
    await user.click(screen.getByRole("button", { name: /ariaLabel/i }));
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Nederlands")).toBeInTheDocument();
    expect(screen.getByText("Română")).toBeInTheDocument();
  });

  it("switches locale on the current path, preserving it", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher variant="nav" />);
    await user.click(screen.getByRole("button", { name: /ariaLabel/i }));
    await user.click(screen.getByText("Română"));
    expect(replace).toHaveBeenCalledWith("/about", { locale: "ro" });
  });

  it("does not navigate when re-selecting the active locale", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher variant="nav" />);
    await user.click(screen.getByRole("button", { name: /ariaLabel/i }));
    await user.click(screen.getByText("English"));
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("LanguageSwitcher (drawer)", () => {
  it("renders the three options inline without a trigger button", () => {
    render(<LanguageSwitcher variant="drawer" />);
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Nederlands")).toBeInTheDocument();
    expect(screen.getByText("Română")).toBeInTheDocument();
  });
});
