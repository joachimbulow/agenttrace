"""AI Agent Step Debugger - FastAPI Application Entry Point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .infrastructure.config import get_settings
from .infrastructure.database import init_db
from .presentation.routers import router as api_router
from .application.dto import HealthResponse


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

# Include API routers
app.include_router(api_router)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Health status.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )