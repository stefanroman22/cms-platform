import { NextRequest, NextResponse } from "next/server";

// Server-side only — not exposed to the browser
const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8001";

async function handler(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const targetPath = "/" + path.join("/");
  const search = request.nextUrl.search;
  const url = `${FASTAPI_URL}${targetPath}${search}`;

  const upstreamHeaders = new Headers();
  const cookie = request.headers.get("cookie");
  if (cookie) upstreamHeaders.set("cookie", cookie);
  const contentType = request.headers.get("content-type");
  if (contentType) upstreamHeaders.set("content-type", contentType);

  const isBodyless = request.method === "GET" || request.method === "HEAD";
  const body = isBodyless ? undefined : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers: upstreamHeaders,
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Auth service unavailable" }, { status: 503 });
  }

  const outHeaders = new Headers();

  // Re-set cookies on localhost:3000 — this is the key fix.
  // Without this, cookies stay scoped to localhost:8001 and the
  // middleware can never read them from incoming browser requests.
  const setCookies = upstream.headers.getSetCookie();
  for (const c of setCookies) {
    // Strip any Domain=... attribute so the browser uses the request host
    // (the frontend custom domain). Without this, the cookie would be
    // scoped to the backend's Vercel URL and not be sent on subsequent
    // frontend requests.
    const cleaned = c.replace(/;\s*Domain=[^;]+/gi, "");
    outHeaders.append("set-cookie", cleaned);
  }

  const ct = upstream.headers.get("content-type");
  if (ct) outHeaders.set("content-type", ct);

  const responseBody = upstream.status === 204 ? null : await upstream.arrayBuffer();

  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: outHeaders,
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
