import { describe, it, expect, vi, afterEach } from "vitest";

import { GET } from "@/app/api/[...path]/route";

// Builds a fake upstream Response good enough for the proxy handler: it reads
// .status, .headers (content-type / cache-control / getSetCookie) and .arrayBuffer().
function mockUpstream(cacheControl?: string) {
  const headers = new Headers({ "content-type": "application/json" });
  if (cacheControl) headers.set("cache-control", cacheControl);
  return vi.fn(async (_url: string | URL | Request, _init?: RequestInit) => ({
    status: 200,
    headers,
    arrayBuffer: async () => new TextEncoder().encode('{"days":[]}').buffer,
  }));
}

// Minimal NextRequest stand-in — the handler only touches method, nextUrl.search,
// and headers.get() for a GET.
function getReq() {
  return {
    method: "GET",
    nextUrl: { search: "?service_id=s1&from=2099-01-01&to=2099-03-01" },
    headers: new Headers(),
  } as unknown as Parameters<typeof GET>[0];
}

function ctx(path: string[]) {
  return { params: Promise.resolve({ path }) } as unknown as Parameters<typeof GET>[1];
}

const CACHE = "s-maxage=30, stale-while-revalidate=60";

afterEach(() => vi.restoreAllMocks());

describe("api proxy — availability edge caching", () => {
  it("forwards the backend Cache-Control for an availability GET", async () => {
    global.fetch = mockUpstream(CACHE) as unknown as typeof fetch;
    const res = await GET(getReq(), ctx(["booking", "acme", "availability"]));
    expect(res.headers.get("cache-control")).toBe(CACHE);
  });

  it("still fetches the backend fresh (upstream stays no-store) on a cache miss", async () => {
    const f = mockUpstream(CACHE);
    global.fetch = f as unknown as typeof fetch;
    await GET(getReq(), ctx(["booking", "acme", "availability"]));
    expect(f.mock.calls[0][1]?.cache).toBe("no-store");
  });

  it("does NOT forward Cache-Control for a non-availability GET", async () => {
    global.fetch = mockUpstream(CACHE) as unknown as typeof fetch;
    const res = await GET(getReq(), ctx(["booking", "acme", "services"]));
    expect(res.headers.get("cache-control")).toBeNull();
  });

  it("does not treat an '/unavailability'-style path as availability", async () => {
    global.fetch = mockUpstream(CACHE) as unknown as typeof fetch;
    const res = await GET(getReq(), ctx(["booking", "acme", "unavailability"]));
    expect(res.headers.get("cache-control")).toBeNull();
  });
});
