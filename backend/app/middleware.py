import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import request_id_var

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation ID to every request and logs method/path/status/duration.

    The ID is echoed back as X-Request-ID so a client-reported error can be traced
    to the exact server-side log line -- the first thing you want when someone
    says "the dashboard broke" and gives you nothing else to go on.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled_exception method=%s path=%s", request.method, request.url.path
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
