import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.logging_config import configure_logging, request_id_var
from app.middleware import RequestContextMiddleware
from app.routers import analytics, chat, predict, reports

configure_logging()
logger = logging.getLogger("app")

app = FastAPI(title="FIFA World Cup 2026 Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Consistent, non-leaky error shape for anything that isn't an HTTPException.

    The traceback goes to logs (keyed by request_id); the client only ever sees the
    correlation ID, never internals -- correct for a public-facing API surface.
    """
    logger.exception("unhandled_exception path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error", "request_id": request_id_var.get()},
    )


app.include_router(analytics.router)
app.include_router(predict.router)
app.include_router(chat.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    """Checks the DB is actually reachable, not just that the process is up --
    what a load balancer / Container Apps health probe should hit."""
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return {"status": "ready"}
    except Exception:
        logger.exception("readiness_check_failed")
        return JSONResponse(status_code=503, content={"status": "not ready"})
