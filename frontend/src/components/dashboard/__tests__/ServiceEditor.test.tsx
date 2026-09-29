import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as cache from "@/lib/cache";

let mockSearch = "";
const { replaceSpy, pushSpy } = vi.hoisted(() => ({ replaceSpy: vi.fn(), pushSpy: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceSpy, push: pushSpy }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => new URLSearchParams(mockSearch),
}));

import { ServiceEditor } from "../ServiceEditor";

const DETAIL = {
  id: "s1",
  service_key: "about",
  label: "About",
  service_type_slug: "text_block",
  service_type_name: "Text block",
  service_type_icon: "type",
  schema: {},
  content: { title: "Hello", body: "World" },
  last_updated: "2026-09-27T10:00:00Z",
  locale: "nl",
  default_locale: "nl",
  locales: ["nl", "en"],
  rich_text_version: 0,
  field_formats: {},
  can_edit_structure: false,
};

function mockFetch(putResponse?: { status: number; body: unknown }) {
  global.fetch = vi.fn().mockImplementation(async (_url: string, init?: RequestInit) => {
    if (init?.method === "PUT" && putResponse) {
      return {
        ok: putResponse.status < 400,
        status: putResponse.status,
        json: async () => putResponse.body,
      };
    }
    return { ok: true, status: 200, json: async () => DETAIL };
  });
}

async function renderAndType() {
  const user = userEvent.setup();
  render(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
  const body = await screen.findByPlaceholderText(/write content here/i);
  await user.type(body, " more");
  return user;
}

function fireBeforeUnload() {
  const ev = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(ev);
  return ev;
}

beforeEach(() => {
  mockSearch = "";
  replaceSpy.mockClear();
  pushSpy.mockClear();
  cache.clearAll();
  mockFetch();
});
afterEach(() => vi.restoreAllMocks());

describe("ServiceEditor unsaved-work guards", () => {
  it("blocks beforeunload only while dirty", async () => {
    render(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
    const body = await screen.findByPlaceholderText(/write content here/i);
    expect(fireBeforeUnload().defaultPrevented).toBe(false);
    await userEvent.setup().type(body, "x");
    expect(fireBeforeUnload().defaultPrevented).toBe(true);
  });

  it("keeps the draft and locale when switching locale is declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = await renderAndType();
    await user.click(screen.getByRole("tab", { name: /en/i }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(replaceSpy).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText(/write content here/i)).toHaveValue("World more");
  });

  it("switches locale when the discard is confirmed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = await renderAndType();
    await user.click(screen.getByRole("tab", { name: /en/i }));
    expect(replaceSpy).toHaveBeenCalledWith(expect.stringContaining("locale=en"), {
      scroll: false,
    });
  });

  it("guards re-translate when dirty", async () => {
    mockSearch = "locale=en";
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...DETAIL, locale: "en" }),
    });
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /re-translate from nl/i }));
    expect(confirmSpy).toHaveBeenCalled();
    const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.some(([u]) => String(u).includes("/retranslate"))).toBe(false);
  });
});

describe("ServiceEditor save errors", () => {
  it("shows a string detail verbatim", async () => {
    mockFetch({
      status: 422,
      body: { detail: "Field title is too long (2001 > 2000 characters)" },
    });
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(
      await screen.findByText("Field title is too long (2001 > 2000 characters)")
    ).toBeInTheDocument();
  });

  it("joins pydantic-style detail messages", async () => {
    mockFetch({ status: 422, body: { detail: [{ msg: "x" }, { msg: "y" }] } });
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(screen.getByText("x; y")).toBeInTheDocument());
  });
});
