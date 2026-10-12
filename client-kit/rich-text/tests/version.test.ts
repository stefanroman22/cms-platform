import { expect, it } from "vitest";
import pkg from "../package.json";
import { RICH_TEXT_KIT_VERSION } from "../src/index";
it("kit version constant matches package.json", () => expect(RICH_TEXT_KIT_VERSION).toBe(pkg.version));
it("kit version is 1.1.0 (styled spans, ADR-0011)", () => expect(RICH_TEXT_KIT_VERSION).toBe("1.1.0"));
