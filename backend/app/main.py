"""FastAPI application entry point for Mission 2."""

import copy
import logging.config
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn.config import LOGGING_CONFIG

from backend.app.routers.chat import router as chat_router
from backend.app.routers.conversations import router as conversations_router
from backend.app.routers.data import router as data_router


LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
)
APPLICATION_INFO_LOGGERS = (
    "backend.app.services.ai",
    "backend.app.services.trend_tools",
)


def _uvicorn_logging_config() -> dict:
    """Keep Uvicorn's handlers and enable safe application INFO messages."""
    config = copy.deepcopy(LOGGING_CONFIG)
    for logger_name in APPLICATION_INFO_LOGGERS:
        config["loggers"][logger_name] = {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        }
    return config


logging.config.dictConfig(_uvicorn_logging_config())


def _allowed_origins() -> list[str]:
    """Read browser origins from a comma-separated environment variable."""
    configured_origins = os.getenv("CORS_ORIGINS", "").strip()
    if not configured_origins:
        return list(LOCAL_ORIGINS)
    return [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]

app = FastAPI(
    title="브랜딩 트렌드 AI 비서 API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(data_router)
app.include_router(conversations_router)
app.include_router(chat_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    del request
    safe_errors = [
        {
            key: value
            for key, value in error.items()
            if key not in {"input", "ctx"}
        }
        for error in exception.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
