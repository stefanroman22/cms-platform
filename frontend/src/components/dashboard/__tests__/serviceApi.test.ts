import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as cache from "@/lib/cache";
import {
  serviceDetailKey,
  serviceDetailPrefix,
  projectStatusKey,
  prefetchServiceDetail,
  saveServiceContent,
} from "../serviceApi";

beforeEach(() => cache.clearAll());
afterEach(() => vi.restoreAllMocks());

describe("keys", () => {
  it("formats detail keys with a default-locale fallback", () => {
    expect(serviceDetailKey("demo", "about")).toBe("service:demo:about:default");
    expect(serviceDetailKey("demo", "about", "en")).toBe("service:demo:about:en");
    expect(serviceDetailPrefix("demo", "about")).toBe("service:demo:about:");
    expect(projectStatusKey("demo")).toBe("status:demo");
  });
});

describe("prefetchServiceDetail", () => {
  it("fetches once and caches under the detail key", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "s1" }) });
    prefetchServiceDetail("demo", "about", "en");
    prefetchServiceDetail("demo", "about", "en");
    await vi.waitFor(() =>
      expect(cache.get(serviceDetailKey("demo", "about", "en"))).toEqual({ id: "s1" })
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/projects/demo/services/about?locale=en"
    );
  });

  it("swallows a failed prefetch without caching or an unhandled rejection", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
    prefetchServiceDetail("demo", "missing");
    await new Promise((r) => setTimeout(r, 20));
    process.off("unhandledRejection", unhandled);
    expect(cache.get(serviceDetailKey("demo", "missing"))).toBeNull();
    expect(cache.getInflight(serviceDetailKey("demo", "missing"))).toBeNull();
    expect(unhandled).not.toHaveBeenCalled();
  });
});

describe("saveServiceContent", () => {
  it("returns the saved detail", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ id: "s1", content: { a: 1 } }) });
    await expect(saveServiceContent("demo", "about", { a: 1 })).resolves.toEqual({
      id: "s1",
      content: { a: 1 },
    });
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/projects/demo/services/about");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ content: { a: 1 } });
  });

  it("maps a string detail to the error message", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: false, json: async () => ({ detail: "Too long" }) });
    await expect(saveServiceContent("demo", "about", {})).rejects.toThrow("Too long");
  });
});
