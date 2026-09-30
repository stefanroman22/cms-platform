import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
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

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function getCalls() {
  return (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
}
const gets = () => getCalls().filter(([, init]) => !init || !init.method || init.method === "GET");
const puts = () => getCalls().filter(([, init]) => init?.method === "PUT");

const SAVED = {
  ...DETAIL,
  content: { title: "Hello", body: "World more" },
  last_updated: "2026-09-30T12:00:00Z",
};

describe("ServiceEditor save flow", () => {
  it("uses the PUT response: no refetch, no remount, clean afterwards", async () => {
    mockFetch({ status: 200, body: SAVED });
    const user = await renderAndType();
    const before = screen.getByPlaceholderText(/write content here/i);
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(await screen.findByText(/changes saved successfully/i)).toBeInTheDocument();
    expect(gets()).toHaveLength(1); // only the initial load
    const after = screen.getByPlaceholderText(/write content here/i);
    expect(after).toBe(before); // same DOM node → editor was not remounted
    expect(after).toHaveValue("World more");
    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument();
    expect(cache.get("service:demo:about:default")).toEqual(SAVED);
  });

  it("keeps text typed while the save is in flight, and stays dirty", async () => {
    const put = deferred<unknown>();
    global.fetch = vi.fn().mockImplementation(async (_u: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        await put.promise;
        return { ok: true, status: 200, json: async () => SAVED };
      }
      return { ok: true, status: 200, json: async () => DETAIL };
    });
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await user.type(screen.getByPlaceholderText(/write content here/i), " again");
    await act(async () => put.resolve(undefined));
    await screen.findByText(/changes saved successfully/i);
    expect(screen.getByPlaceholderText(/write content here/i)).toHaveValue("World more again");
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });

  it("invalidates other locales, the grid list and the publish status", async () => {
    mockFetch({ status: 200, body: SAVED });
    cache.set("service:demo:about:en", { stale: true });
    cache.set("service:demo:hero:en", { other: true });
    const onStatus = vi.fn();
    const onList = vi.fn();
    cache.subscribe("status:demo", onStatus);
    cache.subscribe("services:demo", onList);
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await screen.findByText(/changes saved successfully/i);
    expect(cache.get("service:demo:about:en")).toBeNull();
    expect(cache.get("service:demo:hero:en")).toEqual({ other: true });
    expect(onStatus).toHaveBeenCalled();
    expect(onList).toHaveBeenCalled();
  });

  it("on a failed save keeps the draft and touches no cache", async () => {
    mockFetch({ status: 500, body: { detail: "boom" } });
    cache.set("service:demo:about:en", { keep: true });
    const onStatus = vi.fn();
    cache.subscribe("status:demo", onStatus);
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/write content here/i)).toHaveValue("World more");
    expect(cache.get("service:demo:about:en")).toEqual({ keep: true });
    expect(onStatus).not.toHaveBeenCalled();
  });

  it("Ctrl+S saves once, even when pressed repeatedly during a save", async () => {
    const put = deferred<unknown>();
    global.fetch = vi.fn().mockImplementation(async (_u: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        await put.promise;
        return { ok: true, status: 200, json: async () => SAVED };
      }
      return { ok: true, status: 200, json: async () => DETAIL };
    });
    const user = await renderAndType();
    await user.keyboard("{Control>}s{/Control}");
    await user.keyboard("{Control>}s{/Control}");
    await user.keyboard("{Meta>}s{/Meta}");
    await act(async () => put.resolve(undefined));
    await screen.findByText(/changes saved successfully/i);
    expect(puts()).toHaveLength(1);
  });

  it("does not remount or drop the draft when a background refresh brings a newer version", async () => {
    await renderAndType();
    const before = screen.getByPlaceholderText(/write content here/i);
    act(() => {
      cache.set("service:demo:about:default", { ...DETAIL, last_updated: "2026-09-30T13:00:00Z" });
    });
    const after = screen.getByPlaceholderText(/write content here/i);
    expect(after).toBe(before);
    expect(after).toHaveValue("World more");
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });

  it("remounts with the new content when a newer version arrives while clean", async () => {
    render(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
    await screen.findByPlaceholderText(/write content here/i);
    act(() => {
      cache.set("service:demo:about:default", {
        ...DETAIL,
        content: { title: "Hello", body: "Changed elsewhere" },
        last_updated: "2026-09-30T13:00:00Z",
      });
    });
    expect(await screen.findByDisplayValue("Changed elsewhere")).toBeInTheDocument();
  });

  it("makes the editor inert and disables Save while another locale loads", async () => {
    const { rerender } = render(
      <ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />
    );
    await screen.findByPlaceholderText(/write content here/i);
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {})); // en never resolves
    mockSearch = "locale=en";
    rerender(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("service-editor-body")).toHaveAttribute("inert"));
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
  });
});
