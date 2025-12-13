# =====================================================
# FILE: app/api/api_v1/users/search.py
# User Search Endpoint for Obligation Owner/Escalation Assignment
# =====================================================

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

# Define router with prefix
router = APIRouter(prefix="/api/users", tags=["users"])

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
    job_title: Optional[str] = None
    
    class Config:
        from_attributes = True

# =====================================================
# USER SEARCH ENDPOINT
# =====================================================

@router.get("/search", response_model=List[UserSearchResponse])
async def search_users(
    email: Optional[str] = Query(None, description="Search by email"),
    name: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search users within the same company by email or name.
    Used for assigning obligation owners and escalation contacts.
    """
    try:
        logger.info(f"🔍 Searching users: email={email}, name={name}, company={current_user.company_id}")
        
        # Base query - only active users in the same company
        query = db.query(User).filter(
            User.company_id == current_user.company_id,
            User.is_active == True
        )
        
        # Add email filter (case-insensitive partial match)
        if email:
            query = query.filter(User.email.ilike(f"%{email}%"))
            logger.info(f"  📧 Filtering by email: {email}")
        
        # Add name filter (searches both first and last name)
        if name:
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )
            logger.info(f"  👤 Filtering by name: {name}")
        
        # Limit results and order by name
        users = query.order_by(User.first_name, User.last_name).limit(limit).all()
        
        # Format response
        results = []
        for user in users:
            results.append(UserSearchResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                role=getattr(user, 'user_role', None),
                department=getattr(user, 'department', None),
                job_title=getattr(user, 'job_title', None)
            ))
        
        logger.info(f"✅ Found {len(results)} users")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error searching users: {str(e)}")
        # Return empty list instead of error to prevent breaking the UI
        return []

# =====================================================
# GET USER BY ID
# =====================================================

@router.get("/{user_id}", response_model=UserSearchResponse)
async def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get specific user by ID.
    Used to fetch user details for assigned owners/escalation contacts.
    """
    try:
        logger.info(f"🔍 Fetching user {user_id}")
        
        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == current_user.company_id
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or not in your company"
            )
        
        return UserSearchResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            role=getattr(user, 'user_role', None),
            department=getattr(user, 'department', None),
            job_title=getattr(user, 'job_title', None)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# =====================================================
# GET COMPANY USERS (All)
# =====================================================

@router.get("/company/all", response_model=List[UserSearchResponse])
async def get_all_company_users(
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[str] = Query(None, description="Filter by role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all active users in the same company.
    Useful for populating dropdowns or showing all available users.
    """
    try:
        logger.info(f"📋 Fetching all company users for company {current_user.company_id}")
        
        # Base query
        query = db.query(User).filter(
            User.company_id == current_user.company_id,
            User.is_active == True
        )
        
        # Optional filters
        if department:
            query = query.filter(User.department == department)
        
        if role:
            query = query.filter(User.user_role == role)
        
        users = query.order_by(User.first_name, User.last_name).all()
        
        results = []
        for user in users:
            results.append(UserSearchResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                role=getattr(user, 'user_role', None),
                department=getattr(user, 'department', None),
                job_title=getattr(user, 'job_title', None)
            ))
        
        logger.info(f"✅ Found {len(results)} company users")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error fetching company users: {str(e)}")
        return []