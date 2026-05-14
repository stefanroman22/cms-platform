import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "../LoginForm";
import { AuthProvider } from "@/context/auth";
import { LoadingProvider } from "@/context/loading";

// LoginForm calls router.prefetch("/dashboard") on mount. Stub the router
// so the component can render without a real Next.js app-router context.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ prefetch: vi.fn(), push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/log-in",
  useSearchParams: () => new URLSearchParams(),
}));

// jsdom doesn't ship BroadcastChannel; AuthProvider's logout-sync effect
// uses it. Stub a no-op class for tests.
if (typeof globalThis.BroadcastChannel === "undefined") {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).BroadcastChannel = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    postMessage() {}
    close() {}
  };
}

function renderWithProviders(ui: React.ReactNode) {
  return render(
    <LoadingProvider>
      <AuthProvider>{ui}</AuthProvider>
    </LoadingProvider>
  );
}

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: false });
  Object.defineProperty(document, "cookie", { writable: true, configurable: true, value: "" });
  Object.defineProperty(window, "open", { writable: true, configurable: true, value: vi.fn() });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("LoginForm", () => {
  it("submit button is disabled until both fields are non-empty", async () => {
    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();

    const submit = screen.getByRole("button", { name: /sign in to dashboard/i });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/email/i), "a@b.c");
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/^password$/i), "secret");
    expect(submit).not.toBeDisabled();
  });

  it("toggles password visibility", async () => {
    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();

    const pw = screen.getByLabelText(/^password$/i) as HTMLInputElement;
    expect(pw.type).toBe("password");

    await user.click(screen.getByRole("button", { name: /show password/i }));
    expect(pw.type).toBe("text");
  });

  it("renders error on failed login", async () => {
    // AuthProvider calls getMe() on mount (fetch #1 → ok:false means not logged in).
    // The login submit is fetch #2 — that's the one we want to shape with a detail msg.
    (global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) }) // getMe → not logged in
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid email or password" }),
      }); // login attempt

    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "a@b.c");
    await user.type(screen.getByLabelText(/^password$/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in to dashboard/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });
});
