import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddLeadDrawer } from "./AddLeadDrawer";

describe("AddLeadDrawer", () => {
  it("does not render the form when closed", () => {
    render(<AddLeadDrawer open={false} onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.queryByLabelText("Business name")).not.toBeInTheDocument();
  });

  it("renders a Business name input when open", () => {
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByLabelText("Business name")).toBeInTheDocument();
  });

  it("Add review appends a review row", () => {
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.queryByLabelText("Review 1 author")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /add review/i }));
    expect(screen.getByLabelText("Review 1 author")).toBeInTheDocument();
  });

  it("submitting calls onCreate with business_name and the reviews array", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Business name"), {
      target: { value: "Manual Co" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add review/i }));
    fireEvent.change(screen.getByLabelText("Review 1 author"), {
      target: { value: "Jane" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add lead$/i }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    const payload = onCreate.mock.calls[0][0];
    expect(payload.business_name).toBe("Manual Co");
    expect(Array.isArray(payload.reviews)).toBe(true);
    expect(payload.reviews).toHaveLength(1);
    expect(payload.reviews[0].author).toBe("Jane");
  });

  it("blocks submit with an empty business name", () => {
    const onCreate = vi.fn();
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={onCreate} />);
    fireEvent.click(screen.getByRole("button", { name: /^add lead$/i }));
    expect(onCreate).not.toHaveBeenCalled();
    expect(screen.getByText(/business name is required/i)).toBeInTheDocument();
  });
});
