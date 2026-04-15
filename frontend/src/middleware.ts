import { NextRequest, NextResponse } from "next/server";

const PROTECTED_ROUTES = ["/dashboard"];
const AUTH_ROUTES = ["/log-in"];
const AUTH_SERVICE_URL = process.env.FASTAPI_URL ?? "http://localhost:8001";

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

async function tryRefresh(cookieHeader: string): Promise<Response | null> {
  try {
    const res = await fetch(`${AUTH_SERVICE_URL}/auth/refresh`, {
      method: "POST",
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    return res.ok ? res : null;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_ROUTES.some((r) => pathname.startsWith(r));
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));

  if (!isProtected && !isAuthRoute) return NextResponse.next();

  const cookies = request.cookies;
  const cookieHeader = request.headers.get("cookie") ?? "";

  // ── Fast path: both access_token and auth_verified present ───────────────
  // Skip upstream call entirely — the verified stamp confirms a recent /auth/me
  if (cookies.get("access_token") && cookies.get(VERIFIED_COOKIE)) {
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

  // ── Silent refresh if access token expired ────────────────────────────────
  if (!isAuthenticated) {
    const refreshRes = await tryRefresh(cookieHeader);
    if (refreshRes) {
      isAuthenticated = true;
      const destination = isProtected
        ? NextResponse.next()
        : NextResponse.redirect(new URL("/dashboard", request.url));
      // Forward all Set-Cookie headers from the refresh response
      const newCookies = refreshRes.headers.getSetCookie();
      for (const c of newCookies) {
        destination.headers.append("set-cookie", c);
      }
      markVerified(destination);
      return destination;
    }
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
  matcher: ["/dashboard/:path*", "/log-in"],
};
