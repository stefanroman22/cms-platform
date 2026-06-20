import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import type { BookingStats } from "../api";

// Pin "now" so period labels are deterministic (2026-06-15 is a Monday).
const NOW = new Date("2026-06-15T09:00:00.000Z");

// Stub the chart so we test the range/cursor logic, not recharts.
vi.mock("../OverviewCharts", () => ({
  BookingBreakdown: ({ headerRight }: { headerRight?: ReactNode }) => <div>{headerRight}</div>,
}));
// Stub the query so no network/cache is touched.
vi.mock("@/hooks/useQuery", () => ({
  useQuery: () => ({ data: null, loading: false, error: null }),
}));

import { RangedBreakdown } from "./RangedBreakdown";

const FALLBACK: BookingStats = {
  kpis: { total: 0, upcoming: 0, today: 0, this_week: 0, avg_per_day: 0 },
  cancellation_rate: 0,
  no_show_rate: 0,
  by_day: [],
  by_service: [],
  by_status: [],
  by_staff: [],
  heatmap: [],
} as unknown as BookingStats;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});
afterEach(() => vi.useRealTimers());

function renderRanged() {
  render(<RangedBreakdown projectSlug="demo" fallback={FALLBACK} />);
}

describe("RangedBreakdown period navigation", () => {
  it("has no period navigator for All time (the default)", () => {
    renderRanged();
    expect(screen.getByRole("button", { name: /All time/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Previous period" })).not.toBeInTheDocument();
  });

  it("Day range navigates days with prev/next and a Today reset", () => {
    renderRanged();
    fireEvent.click(screen.getByRole("button", { name: /^Day$/ }));
    expect(screen.getByText(/15 Jun 2026/)).toBeInTheDocument();
    // No "Today" reset while on the current period.
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next period" }));
    expect(screen.getByText(/16 Jun 2026/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous period" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous period" }));
    expect(screen.getByText(/14 Jun 2026/)).toBeInTheDocument();
    // Off the current period → a Today reset appears and returns to today.
    fireEvent.click(screen.getByText("Today"));
    expect(screen.getByText(/15 Jun 2026/)).toBeInTheDocument();
  });

  it("Month range navigates calendar months", () => {
    renderRanged();
    fireEvent.click(screen.getByRole("button", { name: /^Month$/ }));
    expect(screen.getByText("June 2026")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next period" }));
    expect(screen.getByText("July 2026")).toBeInTheDocument();
  });

  it("Year range navigates years; switching range resets the cursor", () => {
    renderRanged();
    fireEvent.click(screen.getByRole("button", { name: /^Year$/ }));
    expect(screen.getByText("2026")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous period" }));
    expect(screen.getByText("2025")).toBeInTheDocument();
    // switching range resets cursor to the current period
    fireEvent.click(screen.getByRole("button", { name: /^Month$/ }));
    expect(screen.getByText("June 2026")).toBeInTheDocument();
  });
});
