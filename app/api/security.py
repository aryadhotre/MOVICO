"""Transport-level hardening: response headers and login rate limiting.

Two concerns that do not belong in any single route live here.

**Headers.** The API returns JSON, never HTML, which makes most of the classic
headers cheap to set and absolute rather than a tuning exercise -- there is no
inline script to allow, no frame to embed, no stylesheet to whitelist.

**Rate limiting.** ``/auth/login`` is the one endpoint where an attacker gets
unlimited free guesses at something valuable. bcrypt already makes each guess
expensive (~100ms), which is also the problem: a few hundred concurrent guesses
saturate a 512 MB instance's CPU and take the whole service down. The limiter
below caps both.

The limiter is in-process and therefore per-instance. On a single free-tier
container that is exactly right; if this ever scales horizontally the counters
should move to Redis, which ``app.services.cache`` is already wired for. A
per-instance limit is still a real limit -- it is not security theatre, it just
multiplies by the instance count.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive headers to every response.

    ``X-Content-Type-Options``
        Stops a browser from MIME-sniffing a JSON response into something
        executable -- the vector behind a JSON response being run as script.
    ``X-Frame-Options`` / ``frame-ancestors``
        Nothing here should ever render in a frame; denying it removes
        clickjacking as a category.
    ``Referrer-Policy``
        Keeps full URLs -- which can carry ids -- out of the Referer header on
        cross-origin navigation.
    ``Content-Security-Policy``
        Scoped to what an API actually needs, which is nothing. ``default-src
        'none'`` means a response that somehow rendered as a document could not
        load a script, a font or an image.
    ``Strict-Transport-Security``
        Production only, and only over HTTPS: sent on a plain-HTTP local response
        it would pin localhost to HTTPS in the developer's browser for a year.
    """

    def __init__(self, app, *, production: bool = False):
        super().__init__(app)
        self.production = production

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"

        # /docs and /redoc are real HTML pages that load Swagger from a CDN, so the
        # blanket policy would break them. They carry no user data.
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            )

        if self.production and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


class SlidingWindowLimiter:
    """Counts hits per key within a sliding window.

    A sliding window rather than a fixed one: fixed windows let a caller spend
    their whole budget at the end of one window and again at the start of the
    next, which is double the intended rate at exactly the moment it matters.

    Memory is bounded by pruning empty deques on each check, so a flood of unique
    keys cannot grow the table without limit.
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> float | None:
        """Records a hit. Returns ``None`` if allowed, else seconds until retry."""
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                retry_after = hits[0] + self.window - now
                return max(retry_after, 1.0)

            hits.append(now)

            # Opportunistic sweep; cheap, and keeps the table proportional to
            # *active* callers rather than to every caller ever seen.
            if len(self._hits) > 2048:
                for stale in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
                    del self._hits[stale]

            return None

    def reset(self, key: str) -> None:
        """Clears a key's history, e.g. after a successful login."""
        with self._lock:
            self._hits.pop(key, None)


#: Five failed attempts a minute per address. Generous for a person who has
#: mistyped a password, useless for a dictionary.
login_limiter = SlidingWindowLimiter(limit=5, window_seconds=60)

#: Account creation is rarer and more expensive; three an hour stops a script
#: filling a 500 MB free-tier database overnight.
register_limiter = SlidingWindowLimiter(limit=3, window_seconds=3600)


def client_address(request: Request) -> str:
    """The caller's address, honouring the proxy header Render sets.

    Behind Render's load balancer every connection appears to come from the proxy,
    so ``request.client.host`` would be a single value shared by all users and the
    first failed login would lock out everyone. ``X-Forwarded-For`` is a chain --
    the leftmost entry is the original client, and entries can be forged by the
    client, but only the ones *before* the proxy's own append. Taking the leftmost
    is the standard trade-off: it is spoofable, which means an attacker can evade
    their own limit, but it never lets one attacker lock out a third party.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(limiter: SlidingWindowLimiter, request: Request, what: str) -> str:
    """Applies a limiter to the caller, raising 429 when exhausted.

    Returns the key so the caller can reset it on success.
    """
    key = client_address(request)
    retry_after = limiter.check(key)
    if retry_after is not None:
        logger.warning("Rate limit hit on %s from %s", what, key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many {what} attempts. Try again in {int(retry_after)} seconds.",
            headers={"Retry-After": str(int(retry_after))},
        )
    return key
