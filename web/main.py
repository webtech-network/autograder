"""FastAPI Web API for the Autograder system."""

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from web.api import api_router
from web.config.body_limit import RequestBodyLimitMiddleware
from web.config.logging import get_logger, setup_logging
from web.config.request_context import (
    REQUEST_ID_HEADER,
    clear_request_id,
    set_request_id,
)
from web.core.host import WebHost
from web.core.lifespan import lifespan

logger = get_logger(__name__)


async def safe_validation_error(request: Request, exc: RequestValidationError):
    # Inputs can contain source code, credentials, or nonfinite numbers. Return paths,
    # stable error types and explanations without echoing the rejected payload.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {
                    "path": list(error["loc"]),
                    "code": error["type"],
                    "message": error["msg"],
                }
                for error in exc.errors()
            ]
        },
    )


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


def create_app(settings=None, *, session_factory=None, capabilities=None,
               resource_owner=None, evaluator=None, start_workers=True):
    host = WebHost(settings, session_factory=session_factory, capabilities=capabilities,
                   resource_owner=resource_owner, evaluator=evaluator, start_workers=start_workers)
    settings = host.settings
    setup_logging(json_logs=settings.JSON_LOGS, service_name=settings.SERVICE_NAME,
                  app_env=settings.APP_ENV, log_level=settings.LOG_LEVEL)
    application = FastAPI(title=settings.API_TITLE, description=settings.API_DESCRIPTION,
                          version=settings.API_VERSION, lifespan=lifespan)
    application.state.host = host
    application.add_exception_handler(RequestValidationError, safe_validation_error)
    application.add_middleware(RequestBodyLimitMiddleware)
    application.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                               allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
                               allow_methods=settings.CORS_ALLOW_METHODS,
                               allow_headers=settings.CORS_ALLOW_HEADERS)
    application.middleware("http")(correlation_logging_middleware)
    application.include_router(api_router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
