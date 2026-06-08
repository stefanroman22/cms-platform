import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import * as cache from "@/lib/cache";
import type { BookingStats } from "../api";

const STATS: BookingStats = {
  kpis: { total: 3, upcoming: 2, today: 1, this_week: 2, avg_per_day: 1.5 },
  cancellation_rate: 0,
  no_show_rate: 0,
  by_day: [],
  by_service: [],
  by_status: [],
  by_staff: [],
  heatmap: [],
};

const getStats = vi.fn().mockResolvedValue(STATS);
const listAppointments = vi.fn().mockResolvedValue({ appointments: [] });
const listServices = vi.fn().mockResolvedValue({ services: [] });
const listResources = vi.fn().mockResolvedValue({ resources: [] });

vi.mock("../api", () => ({
  getStats: (...a: unknown[]) => getStats(...a),
  listAppointments: (...a: unknown[]) => listAppointments(...a),
  listServices: (...a: unknown[]) => listServices(...a),
  listResources: (...a: unknown[]) => listResources(...a),
}));

// AppointmentDetailDrawer is heavy + irrelevant to these assertions.
vi.mock("../AppointmentDetailDrawer", () => ({
  AppointmentDetailDrawer: () => null,
}));

import { OverviewPanel } from "../OverviewPanel";

beforeEach(() => {
  localStorage.clear();
  cache.clearAll();
});
afterEach(() => {
  vi.clearAllMocks();
  cache.clearAll();
});

describe("OverviewPanel", () => {
  // The Calendar widget exposes a "Calendar view" group; the default "Overview"
  // stat view renders an "Upcoming" KPI card.
  const calendarPresent = () => screen.queryByRole("group", { name: /calendar view/i });

  it("always renders the calendar, with the KPI overview as the default stat view", async () => {
    render(<OverviewPanel projectSlug="acme" />);
    await waitFor(() => expect(calendarPresent()).toBeInTheDocument());
    expect(screen.getByText("Upcoming")).toBeInTheDocument();
    // The stat-view filter replaces the old Customize button.
    expect(screen.queryByRole("button", { name: /customize/i })).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: /statistics view/i })).toBeInTheDocument();
  });

  it("selecting a stat view persists across remount; calendar stays put", async () => {
    const { unmount } = render(<OverviewPanel projectSlug="acme" />);
    await waitFor(() => expect(screen.getByText("Upcoming")).toBeInTheDocument());

    // Switch to the Trend view via the segmented filter.
    fireEvent.click(screen.getByRole("button", { name: /^trend$/i }));
    await waitFor(() => expect(screen.getByText(/bookings over time/i)).toBeInTheDocument());

    // Remount → Trend is restored from localStorage (Overview KPIs not shown),
    // and the calendar is still present.
    unmount();
    cache.clearAll();
    render(<OverviewPanel projectSlug="acme" />);
    await waitFor(() => expect(screen.getByText(/bookings over time/i)).toBeInTheDocument());
    expect(calendarPresent()).toBeInTheDocument();
    expect(screen.queryByText("Upcoming")).not.toBeInTheDocument();
  });
});
