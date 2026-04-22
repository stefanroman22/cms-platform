import { NextRequest, NextResponse } from "next/server";

const PROTECTED_ROUTES = ["/dashboard"];
const AUTH_ROUTES = ["/log-in"];
const AUTH_SERVICE_URL = process.env.FASTAPI_URL ?? "http://localhost:8001";

// Canonical host for the CMS admin UI. Any request arriving on the legacy
// Vercel default subdomain (cms-frontend-roman.vercel.app) is permanently
// redirected here so the old URL is effectively unreachable.
const CANONICAL_HOST = "roman-technologies.dev";

// Short-lived middleware-level auth cache cookie.
// Set after a successful /auth/me so we skip the upstream call on every navigation.
// TTL must be shorter than the access token lifetime (15 min) so we never serve
// a stale "verified" stamp after the access token has already expired.
const VERIFIED_COOKIE = "auth_verified";
const VERIFIED_TTL_SECONDS = 13 * 60; // 13 min  (<15 min access token)

function markVerified(response: NextResponse): void {
  response.cookies.set(VERIFIED_COOKIE, "1", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: VERIFIED_TTL_SECONDS,
    // secure only in production — matches the auth cookie behaviour
    secure: process.env.NODE_ENV === "production",
  });
}

function clearVerified(response: NextResponse): void {
  response.cookies.set(VERIFIED_COOKIE, "", { maxAge: 0, path: "/" });
}

export async function middleware(request: NextRequest) {
  // ── Legacy host redirect ────────────────────────────────────────────────
  // Move anyone on the *.vercel.app URL to the custom domain. Runs for
  // every matched path (including the landing page).
  const host = request.headers.get("host") ?? "";
  if (host.startsWith("cms-frontend-roman.") && host.endsWith(".vercel.app")) {
    const url = request.nextUrl.clone();
    url.host = CANONICAL_HOST;
    url.protocol = "https:";
    return NextResponse.redirect(url, 308);
  }

  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_ROUTES.some((r) => pathname.startsWith(r));
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));

  if (!isProtected && !isAuthRoute) return NextResponse.next();

  const cookies = request.cookies;
  const cookieHeader = request.headers.get("cookie") ?? "";

  // ── Fast path: both sid and auth_verified present ───────────────────────
  // Skip upstream call entirely — the verified stamp confirms a recent /auth/me
  if (cookies.get("sid") && cookies.get(VERIFIED_COOKIE)) {
    if (isAuthRoute) return NextResponse.redirect(new URL("/dashboard", request.url));
    return NextResponse.next();
  }

  // ── Slow path: verify with FastAPI ───────────────────────────────────────
  let isAuthenticated = false;
  try {
    const res = await fetch(`${AUTH_SERVICE_URL}/auth/me`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    isAuthenticated = res.ok;
  } catch {
    isAuthenticated = false;
  }

  if (isProtected && !isAuthenticated) {
    const response = NextResponse.redirect(new URL("/log-in", request.url));
    clearVerified(response);
    return response;
  }

  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Authenticated — stamp the verified cookie so next navigation is fast
  const response = NextResponse.next();
  if (isAuthenticated) markVerified(response);
  return response;
}

export const config = {
  // Match every non-static path so the legacy-host redirect runs regardless
  // of which page the visitor is hitting. The auth-flow logic inside the
  // handler early-returns for paths other than /dashboard and /log-in.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico|css|js|woff2?)).*)"],
};
