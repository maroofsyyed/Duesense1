"""
API v1 Router - Combines all v1 endpoints.
"""
from fastapi import APIRouter
from api.v1 import auth, health, deals, ingestion, analytics

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include all sub-routers
router.include_router(auth.router)
router.include_router(health.router)
router.include_router(deals.router)
router.include_router(ingestion.router)
router.include_router(analytics.router)
