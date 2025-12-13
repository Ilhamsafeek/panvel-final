# =====================================================
# FILE: app/api/api_v1/users/search.py
# User Search Endpoint
# =====================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# =====================================================
# SCHEMAS
# =====================================================

class UserSearchResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: Optional[str] = None
    department: Optional[str] = None
    
    class Config:
        from_attributes = True

# =====================================================
# USER SEARCH ENDPOINT
# =====================================================

@router.get("/search", response_model=List[UserSearchResponse])
async def search_users(
    email: Optional[str] = Query(None, description="Search by email"),
    name: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search users within the same company by email or name
    """
    try:
        logger.info(f"🔍 Searching users: email={email}, name={name}")
        
        # Base query - only users in the same company
        query = db.query(User).filter(
            User.company_id == current_user.company_id,
            User.is_active == True
        )
        
        # Add filters
        if email:
            query = query.filter(User.email.ilike(f"%{email}%"))
        
        if name:
            query = query.filter(
                (User.first_name.ilike(f"%{name}%")) |
                (User.last_name.ilike(f"%{name}%"))
            )
        
        # Limit results
        users = query.limit(10).all()
        
        # Format response
        results = [
            UserSearchResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                full_name=f"{user.first_name} {user.last_name}",
                role=user.role_name if hasattr(user, 'role_name') else None,
                department=user.department if hasattr(user, 'department') else None
            )
            for user in users
        ]
        
        logger.info(f"✅ Found {len(results)} users")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error searching users: {str(e)}")
        return []