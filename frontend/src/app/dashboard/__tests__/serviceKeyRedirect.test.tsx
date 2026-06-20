import { Suspense } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, waitFor } from "@testing-library/react";

let mockSearch = "";
const { replaceSpy } = vi.hoisted(() => ({ replaceSpy: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceSpy }),
  useSearchParams: () => new URLSearchParams(mockSearch),
}));

import LegacyServiceEditorRedirect from "../[projectSlug]/[serviceKey]/page";

// The page suspends on its params promise (React `use()`), so the initial
// render must happen inside an awaited act for React to resume it.
async function renderShim() {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <LegacyServiceEditorRedirect
          params={Promise.resolve({ projectSlug: "demo", serviceKey: "hero" })}
        />
      </Suspense>
    );
  });
}

beforeEach(() => {
  mockSearch = "";
  replaceSpy.mockClear();
});

describe("Legacy /dashboard/[projectSlug]/[serviceKey] redirect shim", () => {
  it("redirects old editor links to the inline editor URL", async () => {
    await renderShim();
    await waitFor(() => {
      expect(replaceSpy).toHaveBeenCalledWith("/dashboard/demo?view=cms&service=hero");
    });
  });

  it("preserves the locale of old non-default-locale editor links", async () => {
    mockSearch = "locale=nl";
    await renderShim();
    await waitFor(() => {
      expect(replaceSpy).toHaveBeenCalledWith("/dashboard/demo?view=cms&service=hero&locale=nl");
    });
  });
});
