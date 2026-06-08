// jsdom does not ship IntersectionObserver — provide a no-op stub.
if (typeof globalThis.IntersectionObserver === "undefined") {
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProjectsGrid } from "../ProjectsGrid";

describe("ProjectsGrid", () => {
  it("renders all projects with their key info by default", () => {
    render(<ProjectsGrid />);
    expect(screen.getByText("Akris Website")).toBeInTheDocument();
    expect(screen.getByText("Pluxbox Website")).toBeInTheDocument();
    expect(screen.getByText("Roman Mariana - Business Website")).toBeInTheDocument();
    // keyInfo labels render (each card has a "Type" row).
    expect(screen.getAllByText("Type").length).toBeGreaterThan(0);
  });

  it("filters projects by name", async () => {
    const user = userEvent.setup();
    render(<ProjectsGrid />);
    await user.type(screen.getByLabelText(/search projects/i), "akris");
    expect(screen.getByText("Akris Website")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Pluxbox Website")).not.toBeInTheDocument());
  });

  it("shows an empty state when nothing matches", async () => {
    const user = userEvent.setup();
    render(<ProjectsGrid />);
    await user.type(screen.getByLabelText(/search projects/i), "zzzzz");
    expect(screen.getByText(/no projects match/i)).toBeInTheDocument();
    expect(screen.queryByText("Akris Website")).not.toBeInTheDocument();
  });
});
