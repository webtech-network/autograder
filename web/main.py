"""FastAPI Web API for the Autograder system."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from autograder import __version__
from autograder.models.contracts.definition import validation_error_detail
from sandbox_manager.structured_logging import request_logging_middleware
from web.api import api_router
from web.config.body_limit import RequestBodyLimitMiddleware
from web.config.logging import setup_logging
from web.core.host import WebHost
from web.core.lifespan import lifespan


async def safe_validation_error(request: Request, exc: RequestValidationError):
    # Inputs can contain source code, credentials, or nonfinite numbers. Return paths,
    # stable error types and explanations without echoing the rejected payload. Paths
    # and messages are rendered as compile_definition renders them (the offending field,
    # no pydantic prefix).
    details = []
    for error in exc.errors():
        path, message = validation_error_detail(error)
        details.append({"path": list(path), "code": error["type"], "message": message})
    return JSONResponse(status_code=422, content={"detail": details})


def create_app(settings=None, *, session_factory=None, capabilities=None,
               resource_owner=None, evaluator=None, start_workers=True):
    host = WebHost(settings, session_factory=session_factory, capabilities=capabilities,
                   resource_owner=resource_owner, evaluator=evaluator, start_workers=start_workers)
    settings = host.settings
    setup_logging(json_logs=settings.JSON_LOGS, service_name=settings.SERVICE_NAME,
                  app_env=settings.APP_ENV, log_level=settings.LOG_LEVEL)
    application = FastAPI(title=settings.API_TITLE, description=settings.API_DESCRIPTION,
                          version=__version__, lifespan=lifespan)
    application.state.host = host
    application.add_exception_handler(RequestValidationError, safe_validation_error)
    application.add_middleware(RequestBodyLimitMiddleware)
    application.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                               allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
                               allow_methods=settings.CORS_ALLOW_METHODS,
                               allow_headers=settings.CORS_ALLOW_HEADERS)
    application.middleware("http")(request_logging_middleware)
    application.include_router(api_router)
    return application


# Reads and validates every setting of this host; invalid configuration stops here.
app = create_app()


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--check"]:
        # `python -m web.main --check`: the configuration was accepted above, exactly
        # as at startup (no database, Docker or network access). Deployments run it
        # with the new image before replacing a running API.
        print("Autograder API configuration is valid.")
        sys.exit(0)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
