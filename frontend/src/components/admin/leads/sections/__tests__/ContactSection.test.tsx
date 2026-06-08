import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { ContactSection } from "../ContactSection";
import type { Lead } from "../../types";

const lead = {
  id: "lead-1",
  phone: "+31",
  email: "hi@acme.test",
  website_url: "https://acme.test/",
  facebook_url: null,
  instagram_url: null,
  menu_url: null,
} as unknown as Lead;

describe("ContactSection", () => {
  it("flags invalid email", () => {
    render(
      <EditingSectionProvider>
        <ContactSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    const email = screen.getByLabelText("Email");
    fireEvent.change(email, { target: { value: "broken" } });
    expect(screen.getByText(/valid email/i)).toBeTruthy();
  });

  it("auto-prepends https:// on URL blur", () => {
    render(
      <EditingSectionProvider>
        <ContactSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    const fb = screen.getByLabelText("Facebook URL") as HTMLInputElement;
    fireEvent.change(fb, { target: { value: "facebook.com/acme" } });
    fireEvent.blur(fb);
    expect(fb.value).toBe("https://facebook.com/acme");
  });
});
