import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.logging_config import configure_logging, request_id_var
from app.middleware import RequestContextMiddleware
from app.routers import analytics, charts, chat, predict, reports

configure_logging()
logger = logging.getLogger("app")

if settings.applicationinsights_connection_string:
    # Azure Monitor OpenTelemetry Distro: one call wires up the OpenTelemetry SDK to
    # export to Application Insights and auto-instruments requests/psycopg2 via their
    # standard OTel instrumentation packages. Runs after configure_logging() (not
    # before) because it *adds* a handler to the root logger rather than replacing
    # it, so both destinations (stdout JSON for local/container log streams,
    # Application Insights for the deployed API) stay active together.
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=settings.applicationinsights_connection_string,
        logger_name="app",
    )
    logger.info("application_insights_configured")
else:
    logger.info("application_insights_not_configured")

if settings.sentry_dsn:
    # Sentry: dedicated error tracking (issue grouping, stack traces, breadcrumbs),
    # complementing Application Insights above -- App Insights answers "what's the
    # request volume/latency/DB spans," Sentry answers "an exception happened, here's
    # the full context to debug it." Same env-var-gated, no-op-when-unset pattern.
    # traces_sample_rate=0 -- this project already has dedicated tracing via
    # Application Insights/OpenTelemetry; Sentry here is scoped to error tracking
    # only, not a second, redundant tracing pipeline.
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0)
    logger.info("sentry_configured")
else:
    logger.info("sentry_not_configured")

app = FastAPI(title="FIFA World Cup 2026 Analytics API")

if settings.applicationinsights_connection_string:
    # FastAPI specifically needs this *explicit* call, unlike requests/psycopg2 above.
    # configure_azure_monitor() "auto-instruments" FastAPI by reassigning the
    # `fastapi` module's FastAPI attribute to an instrumented subclass -- but
    # `from fastapi import FastAPI` at the top of this file already bound the
    # *original* class into this module's namespace at import time, before that
    # reassignment happened. Later mutating `fastapi.FastAPI` doesn't retroactively
    # update a name Python already bound elsewhere, so `app = FastAPI(...)` above
    # silently built a plain, uninstrumented app -- no error, just no request span,
    # ever, discovered only because Application Insights' AppRequests table stayed
    # permanently empty while everything else worked. Instrumenting this exact `app`
    # object directly sidesteps the whole import-order trap.
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)

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
    # No explicit sentry_sdk.capture_exception() call needed here, unlike the explicit
    # FastAPIInstrumentor.instrument_app() call required above for Application Insights.
    # Sentry's Starlette/FastAPI integration specifically patches ExceptionMiddleware to
    # re-raise after a custom exception handler like this one runs, purely so its own
    # outer capture point still sees (and reports) the exception -- verified locally: a
    # deliberately triggered error still reached Sentry with this handler in place,
    # confirming the auto-instrumentation, not an explicit call, is what's doing the work.
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error", "request_id": request_id_var.get()},
    )


app.include_router(analytics.router)
app.include_router(predict.router)
app.include_router(chat.router)
app.include_router(reports.router)
app.include_router(charts.router)


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
