"""
Contracts API Package
"""
from fastapi import APIRouter

# Create main contracts router
router = APIRouter()

# Import and include negotiation router
try:
    from app.api.api_v1.contracts.negotiation import router as negotiation_router
    router.include_router(
        negotiation_router, 
        prefix="/negotiation", 
        tags=["negotiation"]
    )
    print("✅ Negotiation router loaded successfully")
except ImportError as e:
    print(f"⚠️ Warning: Could not import negotiation router: {e}")

__all__ = ['router']