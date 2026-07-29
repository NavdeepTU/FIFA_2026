"""A small in-memory rate limiter for the GenAI endpoints.

Hand-rolled rather than a dependency (e.g. slowapi) -- the payoff for one more
package isn't there yet at this project's size (same call made for structured
logging in logging_config.py). In-memory means it only tracks hits within a single
process, which is fine for one Container Apps instance; a distributed store
(Redis) would be the natural upgrade if this ever ran multiple instances.

Fixed-window counter per client IP: MAX_REQUESTS_PER_WINDOW requests per
WINDOW_SECONDS, shared across /chat/retrieve and /chat/ask since both call the
same underlying retrieval and only /ask additionally spends Groq tokens.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 20

_hits: dict[str, list[float]] = defaultdict(list)


def reset() -> None:
    """Test-only: clears all tracked hits so tests don't bleed into each other."""
    _hits.clear()


def rate_limit(request: Request) -> None:
    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS

    hits = _hits[client_key]
    while hits and hits[0] < window_start:
        hits.pop(0)

    if len(hits) >= MAX_REQUESTS_PER_WINDOW:
        retry_after = int(hits[0] + WINDOW_SECONDS - now) + 1
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests -- please wait a moment and try again.",
            headers={"Retry-After": str(retry_after)},
        )

    hits.append(now)
