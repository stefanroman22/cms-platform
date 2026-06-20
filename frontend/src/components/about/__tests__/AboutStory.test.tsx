import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AboutStory } from "../AboutStory";

const STORY: Record<string, unknown> = {
  "story.heading": "Who we are",
  "story.paragraphs": ["First para", "Second para"],
};

vi.mock("next-intl", () => ({
  useTranslations: () => {
    const t = (key: string) => STORY[key] as string;
    t.raw = (key: string) => STORY[key];
    return t;
  },
}));

// jsdom does not ship IntersectionObserver — provide a no-op stub so Reveal
// (whileInView) mounts without throwing.
if (typeof globalThis.IntersectionObserver === "undefined") {
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

describe("AboutStory", () => {
  it("renders the story heading and paragraphs (no values grid)", () => {
    render(<AboutStory />);
    expect(screen.getByRole("heading", { name: "Who we are" })).toBeInTheDocument();
    expect(screen.getByText("First para")).toBeInTheDocument();
    expect(screen.getByText("Second para")).toBeInTheDocument();
  });
});
