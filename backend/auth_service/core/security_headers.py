"""Minimal security headers emitted on every response.

- X-Frame-Options: DENY — prevents the CMS from being rendered inside an
  iframe (clickjacking defense).
- X-Content-Type-Options: nosniff — browser won't MIME-sniff responses
  (guards against content-type confusion attacks).

HSTS is emitted by Vercel's edge layer; not duplicated here.
Content-Security-Policy is intentionally out of scope for v1.
"""


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-content-type-options", b"nosniff"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
