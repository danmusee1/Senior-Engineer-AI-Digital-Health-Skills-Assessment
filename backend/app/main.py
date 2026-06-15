"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestIDMiddleware
from app.db.database import init_db
from app.home.routes import router as home_router
from app.rag.routes import router as rag_router
from app.rag.schemas import ErrorResponse

configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Last Mile Health RAG API",
    description="Retrieval-Augmented Generation API for document Q&A",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware order: Starlette applies middleware in REVERSE order of
# add_middleware() calls (last added = outermost = runs first). We want:
#   CORS (outermost, so preflight/OPTIONS always gets CORS headers)
#   -> RateLimit
#   -> RequestID (innermost, closest to route handlers)
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
    enabled=settings.rate_limit_enabled,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail=str(exc.errors()),
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error.",
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    )


app.include_router(home_router)
app.include_router(rag_router)