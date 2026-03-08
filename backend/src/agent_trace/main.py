"""AI Agent Step Debugger - FastAPI Application Entry Point."""
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .infrastructure.config import get_settings
from .infrastructure.database import init_db
from .presentation.routers import router as api_router
from .application.dto import HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Initializes database on startup.

    Args:
        app: FastAPI application instance.
    """
    settings = get_settings()
    await init_db(settings.database_url)
    yield


app = FastAPI(
    title="Agent Trace",
    description="Local visual debugger for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


# Global exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions with user-friendly messages.
    
    Domain entities raise ValueError for validation failures.
    These should return 400 Bad Request, not 500.
    """
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={
            "error": "validation_error",
            "message": str(exc),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with structured response."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg", "Validation error"),
            "type": error.get("type", "validation_error"),
        })
    
    logger.warning(f"Request validation failed: {errors}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": errors,
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with safe error response.
    
    Prevents stack trace leakage in production.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# Include API routers
app.include_router(api_router)


# Health check endpoint (under /api/v1 for frontend compatibility)
@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Health status.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )


# Also keep root /health for backward compatibility
@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_check_root() -> HealthResponse:
    """Health check endpoint (legacy root path).
    
    Kept for backward compatibility. Prefer /api/v1/health.

    Returns:
        Health status.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )