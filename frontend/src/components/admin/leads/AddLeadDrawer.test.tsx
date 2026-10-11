import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddLeadDrawer } from "./AddLeadDrawer";

describe("AddLeadDrawer", () => {
  it("does not render the form when closed", () => {
    render(<AddLeadDrawer open={false} onClose={vi.fn()} onCreate={vi.fn()} onImport={vi.fn()} />);
    expect(screen.queryByLabelText("Business name")).not.toBeInTheDocument();
  });

  it("renders a Business name input when open", () => {
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={vi.fn()} />);
    expect(screen.getByLabelText("Business name")).toBeInTheDocument();
  });

  it("Add review appends a review row", () => {
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={vi.fn()} />);
    expect(screen.queryByLabelText("Review 1 author")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /add review/i }));
    expect(screen.getByLabelText("Review 1 author")).toBeInTheDocument();
  });

  it("submitting calls onCreate with business_name and the reviews array", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={onCreate} onImport={vi.fn()} />);

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
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={onCreate} onImport={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /^add lead$/i }));
    expect(onCreate).not.toHaveBeenCalled();
    expect(screen.getByText(/business name is required/i)).toBeInTheDocument();
  });

  it("renders the Google import block and calls onImport with input and product", async () => {
    const onImport = vi.fn().mockResolvedValue({ status: "created", lead: { id: "l1" } });
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.change(screen.getByLabelText("Google Maps link, place ID or 'Name, City'"), {
      target: { value: " https://maps.app.goo.gl/abc " },
    });
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    await waitFor(() =>
      expect(onImport).toHaveBeenCalledWith("https://maps.app.goo.gl/abc", "website")
    );
  });

  it("blocks import with an empty input", () => {
    const onImport = vi.fn();
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText(/paste a google maps link/i)).toBeInTheDocument();
  });

  it("shows candidates and re-imports the chosen place id", async () => {
    const onImport = vi
      .fn()
      .mockResolvedValueOnce({
        status: "candidates",
        candidates: [
          { place_id: "ChIJ1", name: "Samir Kapsalon", address: "Stadhuisplein 1" },
          { place_id: "ChIJ2", name: "Samir Barber", address: null },
        ],
      })
      .mockResolvedValueOnce({ status: "created", lead: { id: "l1" } });
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.change(screen.getByLabelText("Google Maps link, place ID or 'Name, City'"), {
      target: { value: "Samir" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    const pick = await screen.findByRole("button", { name: /samir kapsalon/i });
    expect(screen.getByText("Stadhuisplein 1")).toBeInTheDocument();
    fireEvent.click(pick);
    await waitFor(() => expect(onImport).toHaveBeenLastCalledWith("ChIJ1", "website"));
  });

  it("surfaces an import error", async () => {
    const onImport = vi.fn().mockRejectedValue(new Error("Monthly Google import cap reached"));
    render(<AddLeadDrawer open onClose={vi.fn()} onCreate={vi.fn()} onImport={onImport} />);
    fireEvent.change(screen.getByLabelText("Google Maps link, place ID or 'Name, City'"), {
      target: { value: "ChIJx" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));
    expect(await screen.findByText(/monthly google import cap/i)).toBeInTheDocument();
  });
});
