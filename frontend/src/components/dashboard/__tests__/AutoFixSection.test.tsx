import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AutoFixSection } from "../AutoFixSection";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
});
afterEach(() => vi.restoreAllMocks());

describe("AutoFixSection", () => {
  it("renders the Auto-Fix header explaining the agent", () => {
    render(<AutoFixSection projectSlug="demo" isAdmin={false} currentUserId={null} />);
    expect(screen.getByRole("heading", { name: /auto-fix/i })).toBeInTheDocument();
    expect(screen.getByText(/fix it automatically/i)).toBeInTheDocument();
  });
});
