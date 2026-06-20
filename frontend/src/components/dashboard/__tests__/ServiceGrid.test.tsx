import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ServiceCardService } from "../ServiceCard";

let mockSearch = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => new URLSearchParams(mockSearch),
}));

import { ServiceGrid } from "../ServiceGrid";

const SERVICES: ServiceCardService[] = [
  {
    id: "s1",
    service_key: "hero",
    label: "Hero Banner",
    service_type_slug: "text_block",
    service_type_name: "Text Block",
    service_type_icon: "type",
    display_order: 1,
    page_name: "Home",
    last_updated: null,
  },
  {
    id: "s2",
    service_key: "contact-info",
    label: "Contact Info",
    service_type_slug: "text_block",
    service_type_name: "Text Block",
    service_type_icon: "list",
    display_order: 2,
    page_name: "Contact",
    last_updated: null,
  },
];

beforeEach(() => {
  mockSearch = "";
});

function editLinkParams(): URLSearchParams {
  const href = screen.getByRole("link", { name: /edit/i }).getAttribute("href") ?? "";
  expect(href.startsWith("/dashboard/demo?")).toBe(true);
  return new URLSearchParams(href.split("?")[1]);
}

describe("ServiceGrid editHref", () => {
  it("encodes view, the active tab, and the service key into the Edit link", () => {
    mockSearch = "view=cms&tab=Home";
    render(
      <ServiceGrid services={SERVICES} isAdmin={false} removingKey={null} onRemove={vi.fn()} />
    );
    const params = editLinkParams();
    expect(params.get("view")).toBe("cms");
    expect(params.get("tab")).toBe("Home");
    expect(params.get("service")).toBe("hero");
  });

  it("falls back to the first sorted page when no tab param is present", () => {
    render(
      <ServiceGrid services={SERVICES} isAdmin={false} removingKey={null} onRemove={vi.fn()} />
    );
    // Non-General pages sort alphabetically first → "Contact" is the default tab.
    const params = editLinkParams();
    expect(params.get("view")).toBe("cms");
    expect(params.get("tab")).toBe("Contact");
    expect(params.get("service")).toBe("contact-info");
  });
});
