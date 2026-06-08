import { describe, it, expect } from "vitest";
import { NAV_LINKS } from "@/lib/nav-links";

describe("NAV_LINKS", () => {
  it("lists About, Clients, Team, Contact in order with no Projects", () => {
    expect(NAV_LINKS.map((l) => l.label)).toEqual(["About", "Clients", "Team", "Contact"]);
    expect(NAV_LINKS.map((l) => l.href)).toEqual(["/about", "/clients", "/team", "/contact"]);
  });
});
