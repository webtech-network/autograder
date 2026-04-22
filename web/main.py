"""FastAPI Web API for the Autograder system."""

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from web.api import api_router
from web.config.logging import get_logger, setup_logging
from web.config.request_context import REQUEST_ID_HEADER, clear_request_id, set_request_id
from web.core import settings, lifespan


# Setup logging
setup_logging(
    json_logs=settings.JSON_LOGS,
    service_name=settings.SERVICE_NAME,
    app_env=settings.APP_ENV,
    log_level=settings.LOG_LEVEL,
)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


@app.middleware("http")
async def correlation_logging_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER, "").strip() or uuid4().hex[:8]
    set_request_id(request_id)

    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((perf_counter() - start) * 1000)
        logger.exception(
            "http_request_failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": duration_ms,
            },
        )
        clear_request_id()
        raise

    duration_ms = int((perf_counter() - start) * 1000)
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "http_request_completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    clear_request_id()
    return response


# Include API routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
