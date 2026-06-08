import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { CalendarWidget } from "./CalendarWidget";
import type { BookingAppointment, BookingService } from "../api";

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

function appt(id: string, startIso: string, serviceId: string): BookingAppointment {
  return {
    id,
    status: "confirmed",
    start_utc: startIso,
    end_utc: startIso,
    reschedule_count: 0,
    service_id: serviceId,
    customer_name: `Customer ${id}`,
    service_name: serviceId === "s1" ? "Cut" : "Color",
  };
}

const appointments: BookingAppointment[] = [
  appt("a1", "2026-06-10T10:00:00.000Z", "s1"),
  appt("a2", "2026-06-20T14:00:00.000Z", "s2"),
];

function renderWidget(onSelect = vi.fn()) {
  render(
    <CalendarWidget
      appointments={appointments}
      services={services}
      timezone="UTC"
      onSelectAppointment={onSelect}
    />
  );
  return onSelect;
}

describe("CalendarWidget", () => {
  it("renders a month grid with weekday headers by default", () => {
    renderWidget();
    expect(screen.getByText("June 2026")).toBeInTheDocument();
    // Mon-first weekday headers
    expect(screen.getByText("Mo")).toBeInTheDocument();
    expect(screen.getByText("Su")).toBeInTheDocument();
  });

  it("shows event markers for appointments in the month", () => {
    renderWidget();
    // events labelled by customer / service appear as clickable buttons
    expect(screen.getByText(/Customer a1/)).toBeInTheDocument();
    expect(screen.getByText(/Customer a2/)).toBeInTheDocument();
  });

  it("marks today's cell", () => {
    renderWidget();
    const todayCell = screen.getByTestId("calendar-today");
    expect(todayCell).toBeInTheDocument();
    // the 15th is "today" given the pinned clock
    expect(within(todayCell).getByText("15")).toBeInTheDocument();
  });

  it("calls onSelectAppointment when an event is clicked", () => {
    const onSelect = renderWidget();
    fireEvent.click(screen.getByText(/Customer a1/));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].id).toBe("a1");
  });

  it("switches to Day view when the Day toggle is clicked", () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: /^day$/i }));
    expect(screen.getByTestId("calendar-day-view")).toBeInTheDocument();
  });

  it("switches to Week view when the Week toggle is clicked", () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: /^week$/i }));
    expect(screen.getByTestId("calendar-week-view")).toBeInTheDocument();
  });

  it("does not show cancelled appointments", () => {
    const cancelled: BookingAppointment = {
      ...appt("c1", "2026-06-12T10:00:00.000Z", "s1"),
      status: "cancelled",
    };
    render(
      <CalendarWidget
        appointments={[...appointments, cancelled]}
        services={services}
        timezone="UTC"
        onSelectAppointment={vi.fn()}
      />
    );
    // confirmed ones still render…
    expect(screen.getByText(/Customer a1/)).toBeInTheDocument();
    // …but the cancelled one is omitted.
    expect(screen.queryByText(/Customer c1/)).not.toBeInTheDocument();
  });
});
