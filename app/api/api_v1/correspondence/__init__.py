# =====================================================
# FILE: app/api/api_v1/correspondence/__init__.py
# Correspondence Module Initialization
# =====================================================

from fastapi import APIRouter
from .router import router as correspondence_router
from .upload import router as upload_router

# Create main correspondence router
router = APIRouter()

# Include sub-routers
router.include_router(correspondence_router, tags=["Correspondence"])
router.include_router(upload_router, tags=["Correspondence Upload"])

__all__ = ["router"]