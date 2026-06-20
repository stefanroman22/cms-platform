import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { CalendarWidget } from "./CalendarWidget";
import type { BookingAppointment, BookingHour, BookingResource, BookingService } from "../api";

// Pin "now" so "today" and the default month are deterministic.
const NOW = new Date("2026-06-15T09:00:00.000Z");

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});
afterEach(() => {
  vi.useRealTimers();
});

const services: BookingService[] = [
  { id: "s1", name: "Cut", color: "#10b981", duration_min: 30, resource_ids: [] },
  { id: "s2", name: "Color", color: "#3b82f6", duration_min: 60, resource_ids: [] },
];

const staff: BookingResource[] = [{ id: "r1", name: "John", type: "staff", is_active: true }];

function appt(id: string, startIso: string, endIso: string, serviceId: string): BookingAppointment {
  return {
    id,
    status: "confirmed",
    start_utc: startIso,
    end_utc: endIso,
    reschedule_count: 0,
    service_id: serviceId,
    resource_id: "r1",
    customer_name: `Customer ${id}`,
    service_name: serviceId === "s1" ? "Cut" : "Color",
  };
}

const appointments: BookingAppointment[] = [
  appt("a1", "2026-06-10T10:00:00.000Z", "2026-06-10T10:30:00.000Z", "s1"),
  appt("a2", "2026-06-20T14:00:00.000Z", "2026-06-20T15:00:00.000Z", "s2"),
  // Today (the 15th) — appears in the default day timeline.
  appt("a3", "2026-06-15T11:00:00.000Z", "2026-06-15T11:45:00.000Z", "s1"),
  // A SHORT (30-min) booking today — must still show its time · service line.
  appt("a4", "2026-06-15T13:00:00.000Z", "2026-06-15T13:30:00.000Z", "s2"),
];

function renderWidget(onSelect = vi.fn()) {
  render(
    <CalendarWidget
      appointments={appointments}
      services={services}
      staff={staff}
      scope="all"
      timezone="UTC"
      onSelectAppointment={onSelect}
    />
  );
  return onSelect;
}

describe("CalendarWidget", () => {
  it("defaults to the day timeline with a staff column", () => {
    renderWidget();
    expect(screen.getByTestId("calendar-day-view")).toBeInTheDocument();
    // staff column header + today's appointment block
    expect(screen.getByText("John")).toBeInTheDocument();
    expect(screen.getByText(/Customer a3/)).toBeInTheDocument();
  });

  it("shows the time · service line on every block, including a short 30-min one", () => {
    renderWidget();
    // 45-min block
    expect(screen.getByText("11:00 · Cut")).toBeInTheDocument();
    // 30-min block — the secondary line must NOT be gated away by the short height
    expect(screen.getByText(/Customer a4/)).toBeInTheDocument();
    expect(screen.getByText("13:00 · Color")).toBeInTheDocument();
  });

  // ── Schedule-driven day window (NOW = Mon 2026-06-15, weekday 1) ─────────────
  const BIZ_HOURS: BookingHour[] = [
    { resource_id: null, weekday: 1, start_time: "09:00", end_time: "17:00" },
  ];

  function renderHours(scope: string, hours: BookingHour[]) {
    render(
      <CalendarWidget
        appointments={[]}
        services={services}
        staff={staff}
        scope={scope}
        hours={hours}
        timezone="UTC"
        onSelectAppointment={vi.fn()}
      />
    );
  }

  it("All staff → day window follows the business schedule", () => {
    renderHours("all", BIZ_HOURS);
    expect(screen.getByText("09:00")).toBeInTheDocument(); // business opens 09:00
    expect(screen.queryByText("08:00")).not.toBeInTheDocument(); // not the old default-8 start
    expect(screen.getByText("16:00")).toBeInTheDocument(); // last gutter label before 17:00 close
  });

  it("single staff → day window follows that staff's own schedule", () => {
    const withOwn: BookingHour[] = [
      ...BIZ_HOURS,
      { resource_id: "r1", weekday: 1, start_time: "12:00", end_time: "20:00" },
    ];
    renderHours("r1", withOwn);
    expect(screen.getByText("12:00")).toBeInTheDocument(); // John opens at 12:00
    expect(screen.queryByText("09:00")).not.toBeInTheDocument(); // not the business window
  });

  it("single staff with no personal hours inherits the business schedule", () => {
    renderHours("r1", BIZ_HOURS); // r1 has no own rows
    expect(screen.getByText("09:00")).toBeInTheDocument();
  });

  it("shows a Closed state (not a default grid) when the weekday has no hours", () => {
    // Business open Tuesday only (weekday 2); today is Monday → closed.
    renderHours("all", [{ resource_id: null, weekday: 2, start_time: "09:00", end_time: "17:00" }]);
    expect(screen.getByText(/Closed on Mondays/)).toBeInTheDocument();
    expect(screen.queryByText("08:00")).not.toBeInTheDocument(); // no invented default grid
  });

  it("still shows the timeline (not Closed) when a closed day has bookings", () => {
    render(
      <CalendarWidget
        appointments={[appt("x1", "2026-06-15T10:00:00.000Z", "2026-06-15T10:30:00.000Z", "s1")]}
        services={services}
        staff={staff}
        scope="all"
        hours={[{ resource_id: null, weekday: 2, start_time: "09:00", end_time: "17:00" }]}
        timezone="UTC"
        onSelectAppointment={vi.fn()}
      />
    );
    expect(screen.queryByText(/Closed on/)).not.toBeInTheDocument();
    expect(screen.getByText(/Customer x1/)).toBeInTheDocument();
  });

  it("renders a month grid with weekday headers when switched to month", () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: /^month$/i }));
    expect(screen.getByText("June 2026")).toBeInTheDocument();
    expect(screen.getByText("Mo")).toBeInTheDocument();
    expect(screen.getByText("Su")).toBeInTheDocument();
    // events labelled by customer appear as clickable buttons
    expect(screen.getByText(/Customer a1/)).toBeInTheDocument();
    expect(screen.getByText(/Customer a2/)).toBeInTheDocument();
  });

  it("marks today's cell in month view", () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: /^month$/i }));
    const todayCell = screen.getByTestId("calendar-today");
    expect(within(todayCell).getByText("15")).toBeInTheDocument();
  });

  it("calls onSelectAppointment when an event is clicked", () => {
    const onSelect = renderWidget();
    fireEvent.click(screen.getByRole("button", { name: /^month$/i }));
    fireEvent.click(screen.getByText(/Customer a1/));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].id).toBe("a1");
  });

  it("switches to Week view when the Week toggle is clicked", () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: /^week$/i }));
    expect(screen.getByTestId("calendar-week-view")).toBeInTheDocument();
  });

  it("does not show cancelled appointments", () => {
    const cancelled: BookingAppointment = {
      ...appt("c1", "2026-06-15T13:00:00.000Z", "2026-06-15T13:30:00.000Z", "s1"),
      status: "cancelled",
    };
    render(
      <CalendarWidget
        appointments={[...appointments, cancelled]}
        services={services}
        staff={staff}
        scope="all"
        timezone="UTC"
        onSelectAppointment={vi.fn()}
      />
    );
    // confirmed one today still renders…
    expect(screen.getByText(/Customer a3/)).toBeInTheDocument();
    // …but the cancelled one is omitted.
    expect(screen.queryByText(/Customer c1/)).not.toBeInTheDocument();
  });
});
