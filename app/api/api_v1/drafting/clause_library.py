# =====================================================
# FILE: app/api/api_v1/drafting/clause_library.py
# FIXED: Clause Code Generation to prevent duplicates
# Replace the generate_clause_code function and update create_clause
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status, Query 
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from sqlalchemy.exc import IntegrityError
import logging
import uuid
from datetime import datetime
import re

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.clause_library import ClauseLibrary

logger = logging.getLogger(__name__)
router = APIRouter()

# =====================================================
# FIXED: GENERATE UNIQUE CLAUSE CODE
# =====================================================
def generate_clause_code(db: Session, company_id: int) -> str:
    """
    Generate a unique clause code for the company.
    Format: CL####
    Looks for the highest existing number and increments.
    """
    try:
        # Get all clause codes for this company
        existing_codes = db.query(ClauseLibrary.clause_code).filter(
            ClauseLibrary.company_id == company_id,
            ClauseLibrary.clause_code.like('CL%')
        ).order_by(ClauseLibrary.clause_code.desc()).all()
        
        max_number = 0
        
        # Extract numbers from existing codes
        for (code,) in existing_codes:
            # Extract digits from code (e.g., "CL0003" -> "0003" -> 3)
            match = re.search(r'CL(\d+)', code)
            if match:
                number = int(match.group(1))
                max_number = max(max_number, number)
        
        # Generate next code
        next_number = max_number + 1
        new_code = f"CL{str(next_number).zfill(4)}"
        
        logger.info(f" Generated clause code: {new_code} (max was {max_number})")
        return new_code
        
    except Exception as e:
        logger.error(f"❌ Error generating clause code: {str(e)}")
        # Fallback to timestamp-based code
        import time
        fallback_code = f"CL{int(time.time() % 10000):04d}"
        logger.warning(f"⚠️ Using fallback code: {fallback_code}")
        return fallback_code


# =====================================================
# FIXED: CREATE CLAUSE WITH RETRY LOGIC
# =====================================================
@router.post("/clauses", status_code=status.HTTP_201_CREATED)
async def create_clause(
    clause_data: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Create a new clause in the library with duplicate prevention."""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"Creating new clause: {clause_data.get('clause_title')} (attempt {retry_count + 1})")

            # Get company_id
            company_id = current_user.company_id if current_user else None
            if not company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company ID is required"
                )

            # Validate user exists
            created_by_user_id = None
            if current_user and getattr(current_user, "id", None):
                created_by_user_id = str(current_user.id)
                user_exists = db.query(User).filter(User.id == created_by_user_id).first()
                if not user_exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Current user not found in the database."
                    )

            # Generate unique clause code
            clause_code = generate_clause_code(db, company_id)
            
            # Check if code already exists (double-check)
            existing = db.query(ClauseLibrary).filter(
                ClauseLibrary.clause_code == clause_code
            ).first()
            
            if existing:
                logger.warning(f"⚠️ Clause code {clause_code} already exists, retrying...")
                retry_count += 1
                continue

            # Create new clause
            new_clause = ClauseLibrary(
                id=str(uuid.uuid4()),
                company_id=company_id,
                clause_code=clause_code,
                clause_title=clause_data.get('clause_title'),
                clause_title_ar=clause_data.get('clause_title_ar'),
                clause_text=clause_data.get('clause_text'),
                clause_text_ar=clause_data.get('clause_text_ar'),
                category=clause_data.get('category', 'general'),
                sub_category=clause_data.get('sub_category', 'general'),
                clause_type=clause_data.get('clause_type', 'standard'),
                risk_level=clause_data.get('risk_level', 'low'),
                tags=clause_data.get('tags', []),
                is_active=True,
                usage_count=0,
                created_by=created_by_user_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(new_clause)
            db.commit()
            db.refresh(new_clause)
            
            logger.info(f" Clause created successfully: {new_clause.id} - {new_clause.clause_code}")

            return {
                "success": True,
                "message": "Clause created successfully",
                "clause": {
                    "id": new_clause.id,
                    "clause_code": new_clause.clause_code,
                    "clause_title": new_clause.clause_title,
                    "category": new_clause.category,
                    "created_at": new_clause.created_at.isoformat()
                }
            }

        except IntegrityError as e:
            db.rollback()
            logger.error(f"❌ Integrity error: {str(e)}")
            
            # If duplicate key, retry with new code
            if "Duplicate entry" in str(e) and retry_count < max_retries - 1:
                logger.warning(f"⚠️ Duplicate detected, retrying... (attempt {retry_count + 1})")
                retry_count += 1
                continue
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate clause code detected after {retry_count + 1} attempts. Please try again."
            )

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error creating clause: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create clause: {str(e)}"
            )
    
    # If we exhausted all retries
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to generate unique clause code after {max_retries} attempts"
    )


# =====================================================
# GET CLAUSES (Keep existing)
# =====================================================
@router.get("/clauses")
async def get_clauses(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    sort_by: str = Query("recent", regex="^(recent|alphabetical|usage)$"),
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get clauses for current user's company"""
    try:
        logger.info(f"Fetching clauses for user: {current_user.email}")
        query = db.query(ClauseLibrary).filter(
            ClauseLibrary.company_id == current_user.company_id,
            ClauseLibrary.is_active == True
        )
        
        if category:
            query = query.filter(ClauseLibrary.category == category)
        
        if search:
            query = query.filter(
                (ClauseLibrary.clause_title.contains(search)) |
                (ClauseLibrary.clause_text.contains(search))
            )
        
        if sort_by == "recent":
            query = query.order_by(ClauseLibrary.created_at.desc())
        elif sort_by == "alphabetical":
            query = query.order_by(ClauseLibrary.clause_title.asc())
        elif sort_by == "usage":
            query = query.order_by(ClauseLibrary.usage_count.desc())
        
        total = query.count()
        offset = (page - 1) * page_size
        clauses = query.offset(offset).limit(page_size).all()
        
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "clauses": [
                {
                    "id": c.id,
                    "clause_code": c.clause_code,
                    "clause_title": c.clause_title,
                    "clause_text": c.clause_text,
                    "category": c.category,
                    "sub_category": c.sub_category,
                    "clause_type": c.clause_type,
                    "risk_level": c.risk_level,
                    "tags": c.tags,
                    "usage_count": c.usage_count,
                    "created_at": c.created_at.isoformat()
                }
                for c in clauses
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching clauses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clauses: {str(e)}"
        )


# =====================================================
# GET STATISTICS (Keep existing)
# =====================================================
@router.get("/statistics")
async def get_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get clause library statistics"""
    try:
        total_clauses = db.query(ClauseLibrary).filter(
            ClauseLibrary.company_id == current_user.company_id,
            ClauseLibrary.is_active == True
        ).count()
        
        categories = db.query(
            ClauseLibrary.category,
            func.count(ClauseLibrary.id)
        ).filter(
            ClauseLibrary.company_id == current_user.company_id,
            ClauseLibrary.is_active == True
        ).group_by(ClauseLibrary.category).all()
        
        return {
            "success": True,
            "statistics": {
                "total_clauses": total_clauses,
                "categories": {cat: count for cat, count in categories}
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


# =====================================================
# UPDATE CLAUSE
# =====================================================
@router.put("/clauses/{clause_id}", status_code=status.HTTP_200_OK)
async def update_clause(
    clause_id: str,
    clause_data: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Update an existing clause in the library."""
    try:
        logger.info(f"Updating clause: {clause_id}")

        # Find the clause
        clause = db.query(ClauseLibrary).filter(
            ClauseLibrary.id == clause_id,
            ClauseLibrary.company_id == current_user.company_id
        ).first()

        if not clause:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clause not found"
            )

        # Update fields
        if 'clause_title' in clause_data:
            clause.clause_title = clause_data['clause_title']
        if 'clause_title_ar' in clause_data:
            clause.clause_title_ar = clause_data['clause_title_ar']
        if 'clause_text' in clause_data:
            clause.clause_text = clause_data['clause_text']
        if 'clause_text_ar' in clause_data:
            clause.clause_text_ar = clause_data['clause_text_ar']
        if 'category' in clause_data:
            clause.category = clause_data['category']
        if 'sub_category' in clause_data:
            clause.sub_category = clause_data['sub_category']
        if 'clause_type' in clause_data:
            clause.clause_type = clause_data['clause_type']
        if 'risk_level' in clause_data:
            clause.risk_level = clause_data['risk_level']
        if 'tags' in clause_data:
            clause.tags = clause_data['tags']
        if 'is_active' in clause_data:
            clause.is_active = clause_data['is_active']

        clause.updated_at = datetime.utcnow()

        try:
            db.commit()
            db.refresh(clause)
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update clause due to constraint violation."
            )

        logger.info(f" Clause updated successfully: {clause.id}")

        return {
            "success": True,
            "message": "Clause updated successfully",
            "clause": {
                "id": clause.id,
                "clause_code": clause.clause_code,
                "clause_title": clause.clause_title,
                "category": clause.category,
                "updated_at": clause.updated_at.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating clause: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update clause: {str(e)}"
        )


# =====================================================
# DELETE CLAUSE (Soft Delete)
# =====================================================
@router.delete("/clauses/{clause_id}", status_code=status.HTTP_200_OK)
async def delete_clause(
    clause_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Soft delete a clause from the library."""
    try:
        logger.info(f"Deleting clause: {clause_id}")

        # Find the clause
        clause = db.query(ClauseLibrary).filter(
            ClauseLibrary.id == clause_id,
            ClauseLibrary.company_id == current_user.company_id
        ).first()

        if not clause:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clause not found"
            )

        # Soft delete - set is_active to False
        clause.is_active = False
        clause.updated_at = datetime.utcnow()

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete clause"
            )

        logger.info(f" Clause deleted successfully: {clause.id}")

        return {
            "success": True,
            "message": "Clause deleted successfully",
            "clause_id": clause_id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting clause: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete clause: {str(e)}"
        )