from fastapi import APIRouter

from . import ingest, records, runs

router = APIRouter()
router.include_router(runs.router, prefix="/api/v1")
router.include_router(records.router, prefix="/api/v1")
router.include_router(ingest.router, prefix="/api/v1")

__all__ = ["router"]
