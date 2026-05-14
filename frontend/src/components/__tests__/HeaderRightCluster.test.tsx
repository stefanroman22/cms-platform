import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HeaderRightCluster } from "../HeaderRightCluster";
import { AuthProvider } from "@/context/auth";
import { LoadingProvider } from "@/context/loading";

// jsdom does not ship BroadcastChannel — provide a no-op stub so AuthProvider mounts.
if (typeof (globalThis as unknown as Record<string, unknown>).BroadcastChannel === "undefined") {
  (globalThis as unknown as Record<string, unknown>).BroadcastChannel = class {
    onmessage: null = null;
    postMessage() {}
    close() {}
  };
}

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: false });
  Object.defineProperty(document, "cookie", { writable: true, configurable: true, value: "" });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HeaderRightCluster", () => {
  it("renders 'Log In' link when logged out", () => {
    render(
      <LoadingProvider>
        <AuthProvider>
          <HeaderRightCluster />
        </AuthProvider>
      </LoadingProvider>
    );
    expect(screen.getByRole("link", { name: /log in/i })).toBeInTheDocument();
  });

  it("opens mobile drawer when hamburger clicked", async () => {
    const user = userEvent.setup();
    render(
      <LoadingProvider>
        <AuthProvider>
          <HeaderRightCluster />
        </AuthProvider>
      </LoadingProvider>
    );
    await user.click(screen.getByRole("button", { name: /open menu/i }));
    expect(screen.getByRole("button", { name: /close menu/i })).toBeInTheDocument();
  });
});
