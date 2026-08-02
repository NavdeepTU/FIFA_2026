import logging
import time
import uuid

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_config import request_id_var

logger = logging.getLogger("app.request")


class RequestContextMiddleware:
    """Assigns a correlation ID to every request and logs method/path/status/duration.

    The ID is echoed back as X-Request-ID so a client-reported error can be traced
    to the exact server-side log line -- the first thing you want when someone
    says "the dashboard broke" and gives you nothing else to go on.

    Written as a plain ASGI middleware (`__call__(scope, receive, send)`), not a
    `starlette.middleware.base.BaseHTTPMiddleware` subclass, even though the latter
    reads more like typical request/response code. BaseHTTPMiddleware runs the rest
    of the ASGI chain in a separate anyio task to let it intercept a streamed
    response, and Starlette's own docs call out that this breaks contextvars-based
    propagation across that task boundary. FastAPI's OpenTelemetry instrumentation
    relies on exactly that propagation to track the request span from start to
    finish -- with BaseHTTPMiddleware in the stack, the span was silently never
    completing, so Application Insights' `AppRequests` table stayed empty (found via
    the Grafana dashboarding work) even though everything else -- our own structured
    logs, DB call spans -- worked fine, since neither of those cross that same task
    boundary. Plain ASGI middleware runs in the same task as the rest of the chain,
    so the span context stays intact throughout.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception(
                "unhandled_exception method=%s path=%s", scope["method"], scope["path"]
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.1f",
            scope["method"],
            scope["path"],
            status_code,
            duration_ms,
        )
