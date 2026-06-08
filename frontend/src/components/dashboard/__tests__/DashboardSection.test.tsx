import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardSection } from "../DashboardSection";

describe("DashboardSection", () => {
  it("shows the coming-soon analytics empty state", () => {
    render(<DashboardSection onGoToCms={vi.fn()} />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(screen.getByText(/website analytics/i)).toBeInTheDocument();
  });

  it("calls onGoToCms when the shortcut button is clicked", async () => {
    const onGoToCms = vi.fn();
    const user = userEvent.setup();
    render(<DashboardSection onGoToCms={onGoToCms} />);
    await user.click(screen.getByRole("button", { name: /go to cms/i }));
    expect(onGoToCms).toHaveBeenCalledTimes(1);
  });
});
