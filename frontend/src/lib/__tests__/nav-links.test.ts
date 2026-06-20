import { describe, it, expect } from "vitest";
import { NAV_LINKS } from "@/lib/nav-links";

describe("NAV_LINKS", () => {
  it("lists about, clients, team, contact in order with no projects", () => {
    expect(NAV_LINKS.map((l) => l.key)).toEqual(["about", "clients", "team", "contact"]);
    expect(NAV_LINKS.map((l) => l.href)).toEqual(["/about", "/clients", "/team", "/contact"]);
  });
});
