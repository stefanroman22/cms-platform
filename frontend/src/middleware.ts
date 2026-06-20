import { NextRequest, NextResponse } from "next/server";
import createIntlMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/routing";
import {
  resolveLocaleFromCountry,
  hasLocalePrefix,
  stripLocale,
  DEFAULT_LOCALE,
} from "@/lib/locale";

const intlMiddleware = createIntlMiddleware(routing);

const AUTH_SERVICE_URL = process.env.FASTAPI_URL ?? "http://localhost:8001";
const CANONICAL_HOST = "roman-technologies.dev";
const VERIFIED_COOKIE = "auth_verified";
const VERIFIED_TTL_SECONDS = 60;
const LOCALE_COOKIE = "NEXT_LOCALE";
const LOCALE_TTL_SECONDS = 60 * 60 * 24 * 365;

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

async function isAuthenticated(request: NextRequest): Promise<boolean> {
  const cookieHeader = request.headers.get("cookie") ?? "";
  try {
    const res = await fetch(`${AUTH_SERVICE_URL}/auth/me`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}

// Authed users hitting any /log-in (en or prefixed) bounce to the dashboard.
async function maybeRedirectLoggedIn(
  request: NextRequest,
  intlResponse: NextResponse
): Promise<NextResponse> {
  // Exact /log-in match (or a /log-in/* sub-path) — never /log-in-anything-else.
  const path = stripLocale(request.nextUrl.pathname);
  if (path !== "/log-in" && !path.startsWith("/log-in/")) return intlResponse;
  // No session cookie at all → definitely logged out; skip the upstream /auth/me.
  if (!request.cookies.get("sid")) return intlResponse;
  if (request.cookies.get(VERIFIED_COOKIE)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  if (await isAuthenticated(request)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return intlResponse;
}

export async function middleware(request: NextRequest) {
  // ── Legacy host redirect (unchanged) ────────────────────────────────────
  const host = request.headers.get("host") ?? "";
  if (host.startsWith("cms-frontend-roman.") && host.endsWith(".vercel.app")) {
    const url = request.nextUrl.clone();
    url.host = CANONICAL_HOST;
    url.protocol = "https:";
    return NextResponse.redirect(url, 308);
  }

  const { pathname } = request.nextUrl;

  // ── API + widget: never localized, no auth ──────────────────────────────
  if (pathname.startsWith("/api") || pathname.startsWith("/w")) {
    return NextResponse.next();
  }

  // ── Dashboard: locale-free, auth-protected (unchanged semantics) ─────────
  if (pathname.startsWith("/dashboard")) {
    if (request.cookies.get("sid") && request.cookies.get(VERIFIED_COOKIE)) {
      return NextResponse.next();
    }
    if (!(await isAuthenticated(request))) {
      const response = NextResponse.redirect(new URL("/log-in", request.url));
      clearVerified(response);
      return response;
    }
    const response = NextResponse.next();
    markVerified(response);
    return response;
  }

  // ── Marketing area (intl) ────────────────────────────────────────────────
  const firstVisit = !request.cookies.get(LOCALE_COOKIE) && !hasLocalePrefix(pathname);

  if (firstVisit) {
    const locale = resolveLocaleFromCountry(request.headers.get("x-vercel-ip-country"));
    if (locale !== DEFAULT_LOCALE) {
      const url = request.nextUrl.clone();
      url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
      const response = NextResponse.redirect(url);
      response.cookies.set(LOCALE_COOKIE, locale, {
        path: "/",
        maxAge: LOCALE_TTL_SECONDS,
        sameSite: "lax",
      });
      return response;
    }
  }

  const intlResponse = intlMiddleware(request);
  if (firstVisit) {
    // English (or unknown country): pin the cookie so Accept-Language can't override.
    intlResponse.cookies.set(LOCALE_COOKIE, DEFAULT_LOCALE, {
      path: "/",
      maxAge: LOCALE_TTL_SECONDS,
      sameSite: "lax",
    });
  }
  return maybeRedirectLoggedIn(request, intlResponse);
}

export const config = {
  // Match every non-static path so the legacy-host redirect runs regardless
  // of which page the visitor is hitting. The handler routes /api + /w to a
  // pass-through, /dashboard to auth, and everything else through next-intl.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico|css|js|woff2?)).*)",
  ],
};
