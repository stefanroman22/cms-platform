from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_ip(request: Request) -> str:
    """Forwarded-aware client IP extraction.

    The backend runs behind Vercel/Cloudflare, so `request.client.host` is the
    edge IP — every request would share one bucket. Honour the leftmost
    `X-Forwarded-For` value (the original client) and fall back to the peer
    address only if the header is absent.
    """
    fwd = request.headers.get("x-forwarded-for", "").strip()
    if fwd:
        # First entry is the original client; downstream entries are proxy hops.
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
