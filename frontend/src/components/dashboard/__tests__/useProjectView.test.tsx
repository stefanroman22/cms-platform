import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useProjectView } from "../hooks/useProjectView";

const { mockParams, replace } = vi.hoisted(() => ({
  mockParams: { current: new URLSearchParams() },
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => mockParams.current,
}));

beforeEach(() => {
  mockParams.current = new URLSearchParams();
  replace.mockClear();
});

describe("useProjectView", () => {
  it("defaults to dashboard when no view param", () => {
    const { result } = renderHook(() => useProjectView(true));
    expect(result.current.activeView).toBe("dashboard");
  });

  it("honors a valid view param", () => {
    mockParams.current = new URLSearchParams("view=cms");
    const { result } = renderHook(() => useProjectView(true));
    expect(result.current.activeView).toBe("cms");
  });

  it("falls back to dashboard when a non-admin requests settings", () => {
    mockParams.current = new URLSearchParams("view=settings");
    const { result } = renderHook(() => useProjectView(false));
    expect(result.current.activeView).toBe("dashboard");
  });

  it("allows settings for admins", () => {
    mockParams.current = new URLSearchParams("view=settings");
    const { result } = renderHook(() => useProjectView(true));
    expect(result.current.activeView).toBe("settings");
  });

  it("setView preserves the existing tab param", () => {
    mockParams.current = new URLSearchParams("tab=Contact");
    const { result } = renderHook(() => useProjectView(true));
    act(() => result.current.setView("cms"));
    expect(replace).toHaveBeenCalledTimes(1);
    const url = replace.mock.calls[0][0] as string;
    expect(url).toContain("view=cms");
    expect(url).toContain("tab=Contact");
    expect(replace.mock.calls[0][1]).toEqual({ scroll: false });
  });
});
