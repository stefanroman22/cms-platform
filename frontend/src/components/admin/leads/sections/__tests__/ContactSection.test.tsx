import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

  it("keeps typed edits when the parent re-renders with an equal lead", () => {
    const withSocial = {
      ...lead,
      social_links: { facebook: "https://facebook.com/acme" },
    } as Lead;
    const { rerender } = render(
      <EditingSectionProvider>
        <ContactSection lead={withSocial} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+32 999" } });
    rerender(
      <EditingSectionProvider>
        <ContactSection
          lead={{ ...withSocial, social_links: { ...withSocial.social_links } } as Lead}
          onPatched={vi.fn()}
        />
      </EditingSectionProvider>
    );
    expect((screen.getByLabelText("Phone") as HTMLInputElement).value).toBe("+32 999");
  });

  it("sends social_links as a full map when a social URL changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => lead });
    vi.stubGlobal("fetch", fetchMock);
    const withSocial = {
      ...lead,
      facebook_url: "https://facebook.com/acme",
      social_links: { facebook: "https://facebook.com/acme" },
    } as Lead;
    render(
      <EditingSectionProvider>
        <ContactSection lead={withSocial} onPatched={vi.fn()} />
      </EditingSectionProvider>
    );
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    fireEvent.change(screen.getByLabelText("TikTok URL"), {
      target: { value: "tiktok.com/@acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.social_links).toEqual({
      facebook: "https://facebook.com/acme",
      tiktok: "https://tiktok.com/@acme",
    });
    expect(body.facebook_url).toBeUndefined();
    vi.unstubAllGlobals();
  });
});
