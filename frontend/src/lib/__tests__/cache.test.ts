import { describe, it, expect, beforeEach, vi } from "vitest";
import * as cache from "@/lib/cache";

beforeEach(() => cache.clearAll());

describe("invalidatePrefix", () => {
  it("removes matching keys, keeps the excepted key and others, and notifies", () => {
    cache.set("service:demo:about:default", 1);
    cache.set("service:demo:about:en", 2);
    cache.set("service:demo:hero:en", 3);
    cache.set("services:demo", 4);
    const onEn = vi.fn();
    const onDefault = vi.fn();
    cache.subscribe("service:demo:about:en", onEn);
    cache.subscribe("service:demo:about:default", onDefault);

    cache.invalidatePrefix("service:demo:about:", { except: "service:demo:about:default" });

    expect(cache.get("service:demo:about:en")).toBeNull();
    expect(cache.get("service:demo:about:default")).toBe(1);
    expect(cache.get("service:demo:hero:en")).toBe(3);
    expect(cache.get("services:demo")).toBe(4);
    expect(onEn).toHaveBeenCalledTimes(1);
    expect(onDefault).not.toHaveBeenCalled();
  });

  it("is a no-op when nothing matches", () => {
    cache.set("services:demo", 4);
    expect(() => cache.invalidatePrefix("service:nope:")).not.toThrow();
    expect(cache.get("services:demo")).toBe(4);
  });
});
