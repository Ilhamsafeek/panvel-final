# =====================================================
# FILE: app/api/api_v1/users/users.py
# Complete Users API Router - All Endpoints with Expert Profile Support
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text
from typing import Optional, List
from datetime import datetime
import logging
import bcrypt
import secrets


from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, Company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

# =====================================================
# HELPER FUNCTIONS FOR EXPERT PROFILES
# =====================================================

def create_expert_profile(db: Session, user_id: int, profile_data: dict):
    """Create expert profile in database"""
    try:
        insert_query = text("""
            INSERT INTO expert_profiles (
                user_id, specialization, years_of_experience, 
                license_number, license_authority, hourly_rate,
                expertise_areas, bio, qfcra_certified, qid_verified,
                is_available, total_consultations, average_rating,
                created_at, updated_at
            ) VALUES (
                :user_id, :specialization, :years_of_experience,
                :license_number, :license_authority, :hourly_rate,
                :expertise_areas, :bio, :qfcra_certified, :qid_verified,
                :is_available, 0, 0.0,
                NOW(), NOW()
            )
        """)
        
        db.execute(insert_query, {
            "user_id": user_id,
            "specialization": profile_data.get("specialization"),
            "years_of_experience": profile_data.get("years_of_experience"),
            "license_number": profile_data.get("license_number"),
            "license_authority": profile_data.get("license_authority"),
            "hourly_rate": profile_data.get("hourly_rate"),
            "expertise_areas": profile_data.get("expertise_areas"),
            "bio": profile_data.get("bio"),
            "qfcra_certified": profile_data.get("qfcra_certified", False),
            "qid_verified": profile_data.get("qid_verified", False),
            "is_available": profile_data.get("is_available", True)
        })
        db.commit()
        logger.info(f"✅ Expert profile created for user_id: {user_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating expert profile: {str(e)}")
        raise

def update_expert_profile(db: Session, user_id: int, profile_data: dict):
    """Update or create expert profile"""
    try:
        # Check if profile exists
        check_query = text("SELECT id FROM expert_profiles WHERE user_id = :user_id")
        result = db.execute(check_query, {"user_id": user_id}).fetchone()
        
        if result:
            # Update existing profile
            update_query = text("""
                UPDATE expert_profiles SET
                    specialization = :specialization,
                    years_of_experience = :years_of_experience,
                    license_number = :license_number,
                    license_authority = :license_authority,
                    hourly_rate = :hourly_rate,
                    expertise_areas = :expertise_areas,
                    bio = :bio,
                    qfcra_certified = :qfcra_certified,
                    qid_verified = :qid_verified,
                    is_available = :is_available,
                    updated_at = NOW()
                WHERE user_id = :user_id
            """)
            
            db.execute(update_query, {
                "user_id": user_id,
                "specialization": profile_data.get("specialization"),
                "years_of_experience": profile_data.get("years_of_experience"),
                "license_number": profile_data.get("license_number"),
                "license_authority": profile_data.get("license_authority"),
                "hourly_rate": profile_data.get("hourly_rate"),
                "expertise_areas": profile_data.get("expertise_areas"),
                "bio": profile_data.get("bio"),
                "qfcra_certified": profile_data.get("qfcra_certified", False),
                "qid_verified": profile_data.get("qid_verified", False),
                "is_available": profile_data.get("is_available", True)
            })
            logger.info(f"✅ Expert profile updated for user_id: {user_id}")
        else:
            # Create new profile
            create_expert_profile(db, user_id, profile_data)
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error updating expert profile: {str(e)}")
        raise

def delete_expert_profile(db: Session, user_id: int):
    """Delete expert profile or mark as unavailable"""
    try:
        delete_query = text("DELETE FROM expert_profiles WHERE user_id = :user_id")
        db.execute(delete_query, {"user_id": user_id})
        db.commit()
        logger.info(f"✅ Expert profile deleted for user_id: {user_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error deleting expert profile: {str(e)}")
        return False

# =====================================================
# GET COMPANY USERS ENDPOINT (for your frontend)
# =====================================================
@router.get("/company")
async def get_company_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by name or email"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    role_filter: Optional[str] = Query(None, description="Filter by role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get users for company
    - Internal users: See ALL users across all companies WITH company names
    - Regular users: See only users from their company
    """
    try:
        logger.info(f"Fetching company users with skip={skip}, limit={limit}")
        
        # Build base query with LEFT JOIN to companies table        
        query = db.query(
            User,
            Company.company_name.label('company_name')
        ).outerjoin(Company, User.company_id == Company.id)
        
        # ✅ INTERNAL USER CHECK - Show all users if internal
        if current_user.user_type != 'internal':
            # Not internal user - filter by company_id
            if current_user.company_id:
                query = query.filter(User.company_id == current_user.company_id)
                logger.info(f"Filtering by company_id={current_user.company_id} for non-internal user")
            else:
                # User has no company - return empty
                logger.warning(f"User {current_user.id} has no company_id")
                return {
                    "users": [],
                    "total": 0,
                    "skip": skip,
                    "limit": limit
                }
        else:
            logger.info(f"Internal user {current_user.id} - showing all users with company names")
        
        # Apply search filter
        if search:
            search_term = f"%{search.lower()}%"
            search_filter = or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term),
                User.username.ilike(search_term),
                User.job_title.ilike(search_term),
                Company.company_name.ilike(search_term)  # Search by company name too
            )
            query = query.filter(search_filter)
        
        # Apply status filter
        if status_filter:
            if status_filter == "active":
                query = query.filter(and_(User.is_active == True, User.is_verified == True))
            elif status_filter == "inactive":
                query = query.filter(or_(User.is_active == False, User.is_verified == False))
            elif status_filter == "pending":
                query = query.filter(User.is_verified == False)
        
        # Apply role filter
        if role_filter:
            query = query.filter(User.user_role == role_filter)
        
        # Get total count
        total_users = query.count()
        
        # Get users with pagination
        results = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        
        # Convert to the format your frontend expects
        user_list = []
        for user, company_name in results:
            user_data = {
                "id": user.id,
                "company_id": user.company_id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "email": user.email or "",
                "username": user.username or "",
                "user_role": user.user_role or "user",
                "department": user.department or "",
                "job_title": user.job_title or "",
                "mobile_number": user.mobile_number or "",
                "qid_number": user.qid_number or "",
                "user_type": user.user_type or "client",
                "language_preference": user.language_preference or "en",
                "timezone": user.timezone or "Asia/Qatar",
                "is_active": bool(user.is_active) if user.is_active is not None else True,
                "is_verified": bool(user.is_verified) if user.is_verified is not None else True,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                # ✅ Add company name (only meaningful for internal users viewing multiple companies)
                "company_name": company_name or "N/A"
            }
            user_list.append(user_data)
        
        logger.info(f"Successfully returning {len(user_list)} users (total: {total_users})")
        
        return {
            "users": user_list,
            "total": total_users,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error in get_company_users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

# =====================================================
# CREATE USER ENDPOINT (Enhanced with Expert Profile Support)
# =====================================================
@router.post("/create")
async def create_user(
    user_data: dict,  # Accept dict for simplicity
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """
    Create a new user with optional expert profile
    TEMPORARILY WITHOUT AUTHENTICATION FOR TESTING
    """
    try:
        logger.info(f"Creating user: {user_data.get('email', 'unknown')}")
        
        # Validate required fields
        if not user_data.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )
        
        if not user_data.get("password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required"
            )
        
        if not user_data.get("first_name"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="First name is required"
            )
        
        if not user_data.get("last_name"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Last name is required"
            )
        
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == user_data["email"]).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already exists"
            )
        
        # Generate username if not provided
        username = user_data.get("username")
        if not username:
            username = user_data["email"].split('@')[0]
        
        # Make username unique if needed
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            username = f"{username}_{secrets.randbelow(1000)}"
        
        # Hash password
        password = user_data["password"]
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        
        # Get or create default company
        company_id = 1  # Default company ID for testing
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            logger.info("Creating default company")
            new_company = Company(
                id=1,
                company_name="Default Company",
                email="admin@company.com",
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(new_company)
            db.commit()
        
        # Create new user
        new_user = User(
            company_id=company_id,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            email=user_data["email"],
            username=username,
            password_hash=hashed_password,
            user_role=user_data.get("user_role", "user"),
            department=user_data.get("department"),
            job_title=user_data.get("job_title"),
            mobile_number=user_data.get("mobile_number"),
            mobile_country_code="+974",
            qid_number=user_data.get("qid_number"),
            user_type=user_data.get("user_type", "client"),
            language_preference=user_data.get("language_preference", "en"),
            timezone=user_data.get("timezone", "Asia/Qatar"),
            is_active=user_data.get("is_active", True),
            is_verified=True,
            created_at=datetime.utcnow()
        )
        
        logger.info(f"Saving user to database: {new_user.email}")
        
        # Save to database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"User created successfully with ID: {new_user.id}")
        
        # Create expert profile if user_type is expert
        is_expert = False
        if user_data.get("user_type") == "expert" and user_data.get("expert_profile"):
            try:
                create_expert_profile(db, new_user.id, user_data["expert_profile"])
                is_expert = True
                logger.info(f"✅ Expert profile created for user {new_user.id}")
            except Exception as e:
                logger.error(f"❌ Failed to create expert profile: {str(e)}")
                # Don't fail the entire user creation, just log the error
        
        return {
            "success": True,
            "message": "User created successfully",
            "user_id": new_user.id,
            "email": new_user.email,
            "is_expert": is_expert,
            "data": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "user_type": new_user.user_type
            }
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get("/search")
async def search_users(
    email: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search users within the same company by email or name.
    Used for obligation owner/escalation assignment.
    """
    try:
        logger.info(f"🔍 Searching users: email={email}, name={name}")
        
        # Base query - only active users in same company
        query = db.query(User).filter(
            User.company_id == current_user.company_id,
            User.is_active == True
        )
        
        # Add email filter
        if email:
            query = query.filter(User.email.ilike(f"%{email}%"))
            logger.info(f"  📧 Filtering by email: {email}")
        
        # Add name filter
        if name:
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{name}%"),
                    User.last_name.ilike(f"%{name}%")
                )
            )
            logger.info(f"  👤 Filtering by name: {name}")
        
        # Get results
        users = query.order_by(User.first_name, User.last_name).limit(10).all()
        
        # Format response
        results = []
        for user in users:
            results.append({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "role": getattr(user, 'user_role', None),
                "department": getattr(user, 'department', None),
                "job_title": getattr(user, 'job_title', None)
            })
        
        logger.info(f"✅ Found {len(results)} users")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error searching users: {str(e)}")
        return []  # Return empty list instead of error to prevent UI break


# =====================================================
# EXISTING: GET USERS ENDPOINT (your original code)
# =====================================================
@router.get("/")
async def get_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    user_type: Optional[str] = Query(None, description="Filter by user type"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """
    Get list of users with filtering options - YOUR ORIGINAL ENDPOINT
    """
    try:
        # For testing without authentication, comment out user restriction
        # logger.info(f"Fetching users for: {current_user.email}")
        
        # Build filters
        filters = []
        
        # Filter by company (users can only see users from their company)
        # TEMPORARILY DISABLED FOR TESTING:
        # if current_user.company_id:
        #     filters.append(User.company_id == current_user.company_id)
        
        # Filter by specific company_id (if provided)
        if company_id is not None:
            filters.append(User.company_id == company_id)
        
        # Filter by user type
        if user_type:
            filters.append(User.user_type == user_type)
        
        # Filter by active status
        if is_active is not None:
            filters.append(User.is_active == is_active)
        
        # Search filter
        if search:
            search_filter = or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
            filters.append(search_filter)
        
        # Build query
        query = db.query(User)
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        users = query.offset(offset).limit(limit).all()
        
        # Convert to dict
        result = []
        for user in users:
            # Get company name
            company_name = None
            if user.company_id:
                company = db.query(Company).filter(Company.id == user.company_id).first()
                if company:
                    company_name = company.company_name
            
            result.append({
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": f"{user.first_name} {user.last_name}",
                "user_type": user.user_type,
                "department": user.department,
                "job_title": user.job_title,
                "company_id": user.company_id,
                "company_name": company_name,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "mobile_number": user.mobile_number,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
            })
        
        return {
            "success": True,
            "data": result,
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(result)
        }
        
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

# =====================================================
# EXISTING: GET SINGLE USER ENDPOINT (your original code)
# =====================================================
@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific user - YOUR ORIGINAL ENDPOINT
    """
    try:
        logger.info(f"Fetching user: {user_id}")
        
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Check if current user has permission to view this user
        # TEMPORARILY DISABLED FOR TESTING:
        # if current_user.company_id != user.company_id:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="You don't have permission to view this user"
        #     )
        
        # Get company info
        company_name = None
        if user.company_id:
            company = db.query(Company).filter(Company.id == user.company_id).first()
            if company:
                company_name = company.company_name
        
        return {
            "success": True,
            "data": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "first_name_ar": user.first_name_ar,
                "last_name_ar": user.last_name_ar,
                "qid_number": user.qid_number,
                "mobile_number": user.mobile_number,
                "mobile_country_code": user.mobile_country_code,
                "user_type": user.user_type,
                "department": user.department,
                "job_title": user.job_title,
                "company_id": user.company_id,
                "company_name": company_name,
                "language_preference": user.language_preference,
                "timezone": user.timezone,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "user_role": user.user_role,
                "two_factor_enabled": user.two_factor_enabled,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "profile_picture_url": user.profile_picture_url
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user: {str(e)}"
        )

# =====================================================
# NEW: GET EXPERT PROFILE ENDPOINT
# =====================================================
@router.get("/expert-profiles/{user_id}")
async def get_expert_profile(
    user_id: int,
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """Get expert profile by user ID"""
    try:
        query = text("""
            SELECT id, user_id, specialization, years_of_experience,
                   license_number, license_authority, hourly_rate,
                   expertise_areas, bio, is_available, qfcra_certified,
                   qid_verified, total_consultations, average_rating
            FROM expert_profiles
            WHERE user_id = :user_id
        """)
        
        result = db.execute(query, {"user_id": user_id}).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expert profile not found"
            )
        
        profile_dict = {
            "id": result[0],
            "user_id": result[1],
            "specialization": result[2],
            "years_of_experience": result[3],
            "license_number": result[4],
            "license_authority": result[5],
            "hourly_rate": float(result[6]) if result[6] else None,
            "expertise_areas": result[7],
            "bio": result[8],
            "is_available": bool(result[9]) if result[9] is not None else True,
            "qfcra_certified": bool(result[10]) if result[10] is not None else False,
            "qid_verified": bool(result[11]) if result[11] is not None else False,
            "total_consultations": result[12] or 0,
            "average_rating": float(result[13]) if result[13] else 0.0
        }
        
        return profile_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching expert profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch expert profile: {str(e)}"
        )

# =====================================================
# UPDATE USER ENDPOINT (Enhanced with Expert Profile Support)
# =====================================================
@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user_data: dict,
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """
    Update an existing user with optional expert profile
    TEMPORARILY WITHOUT AUTHENTICATION FOR TESTING
    """
    try:
        logger.info(f"Updating user: {user_id}")
        
        # Get the user to update
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if current user has permission to update this user
        # TEMPORARILY DISABLED FOR TESTING:
        # if current_user.company_id != user.company_id:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="You don't have permission to update this user"
        #     )
        
        # Check email uniqueness if changed
        if user_data.get("email") and user_data["email"] != user.email:
            existing_email = db.query(User).filter(
                and_(
                    User.email == user_data["email"],
                    User.id != user_id
                )
            ).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address already exists"
                )
        
        # Check username uniqueness if changed
        if user_data.get("username") and user_data["username"] != user.username:
            existing_username = db.query(User).filter(
                and_(
                    User.username == user_data["username"],
                    User.id != user_id
                )
            ).first()
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
        
        # Update user fields
        update_fields = [
            'first_name', 'last_name', 'email', 'username', 'user_role',
            'department', 'job_title', 'mobile_number', 'qid_number',
            'user_type', 'language_preference', 'timezone'
        ]
        
        for field in update_fields:
            if field in user_data and user_data[field] is not None:
                setattr(user, field, user_data[field])
        
        if 'is_active' in user_data:
            user.is_active = user_data['is_active']
        
        # Update password if provided
        if user_data.get("password"):
            password_bytes = user_data["password"].encode('utf-8')
            salt = bcrypt.gensalt()
            user.password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        
        # Update metadata
        user.updated_at = datetime.utcnow()
        
        # Save changes
        db.commit()
        db.refresh(user)
        
        logger.info(f"User {user_id} updated successfully")
        
        # Handle expert profile
        if user_data.get("user_type") == "expert" and user_data.get("expert_profile"):
            try:
                update_expert_profile(db, user_id, user_data["expert_profile"])
                logger.info(f"✅ Expert profile updated for user {user_id}")
            except Exception as e:
                logger.error(f"❌ Failed to update expert profile: {str(e)}")
                # Don't fail the entire update, just log the error
        elif user_data.get("user_type") and user_data.get("user_type") != "expert":
            # If user type changed from expert to something else, mark profile as unavailable
            try:
                unavailable_query = text("""
                    UPDATE expert_profiles 
                    SET is_available = 0, updated_at = NOW()
                    WHERE user_id = :user_id
                """)
                db.execute(unavailable_query, {"user_id": user_id})
                db.commit()
            except Exception as e:
                logger.error(f"Error deactivating expert profile: {str(e)}")
        
        return {
            "success": True,
            "message": "User updated successfully",
            "data": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "user_type": user.user_type
            }
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

# =====================================================
# DELETE USER ENDPOINT (Enhanced to handle expert profiles)
# =====================================================
@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """
    Delete a user (soft delete) - Also handles expert profile deletion
    TEMPORARILY WITHOUT AUTHENTICATION FOR TESTING
    """
    try:
        logger.info(f"Deleting user: {user_id}")
        
        # Get the user to delete
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if current user has permission to delete this user
        # TEMPORARILY DISABLED FOR TESTING:
        # if current_user.company_id != user.company_id:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="You don't have permission to delete this user"
        #     )
        
        # Prevent self-deletion
        # TEMPORARILY DISABLED FOR TESTING:
        # if current_user.id == user_id:
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail="Cannot delete your own account"
        #     )
        
        # Delete expert profile if exists (cascade should handle this, but being explicit)
        if user.user_type == "expert":
            try:
                delete_expert_profile(db, user_id)
            except Exception as e:
                logger.error(f"Error deleting expert profile: {str(e)}")
        
        # Soft delete by deactivating the user
        user.is_active = False
        user.updated_at = datetime.utcnow()
        
        # Optionally add deletion marker to email
        if not user.email.endswith('.deleted'):
            user.email = f"{user.email}.deleted.{int(datetime.utcnow().timestamp())}"
        
        db.commit()
        
        logger.info(f"User {user_id} deleted successfully")
        
        return {
            "success": True,
            "message": "User deleted successfully"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

# =====================================================
# EXISTING: GET CURRENT USER PROFILE (your original code)
# =====================================================
@router.get("/me/profile")
async def get_current_user_profile(
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current logged-in user's profile information - YOUR ORIGINAL ENDPOINT
    """
    try:
        # For testing, return a mock user profile
        # Later uncomment the authentication and use real current_user
        
        # Mock user for testing
        mock_user = {
            "id": 1,
            "email": "admin@test.com",
            "username": "admin",
            "first_name": "Admin",
            "last_name": "User",
            "full_name": "Admin User",
            "user_type": "admin",
            "department": "IT",
            "job_title": "Administrator",
            "company_id": 1,
            "company_name": "Test Company",
            "mobile_number": "+97412345678",
            "profile_picture_url": None,
            "language_preference": "en",
            "timezone": "Asia/Qatar",
            "two_factor_enabled": False
        }
        
        return {
            "success": True,
            "data": mock_user
        }
        
        # UNCOMMENT THIS WHEN AUTHENTICATION IS RE-ENABLED:
        # # Get company info
        # company_name = None
        # if current_user.company_id:
        #     company = db.query(Company).filter(Company.id == current_user.company_id).first()
        #     if company:
        #         company_name = company.company_name
        # 
        # return {
        #     "success": True,
        #     "data": {
        #         "id": current_user.id,
        #         "email": current_user.email,
        #         "username": current_user.username,
        #         "first_name": current_user.first_name,
        #         "last_name": current_user.last_name,
        #         "full_name": f"{current_user.first_name} {current_user.last_name}",
        #         "user_type": current_user.user_type,
        #         "department": current_user.department,
        #         "job_title": current_user.job_title,
        #         "company_id": current_user.company_id,
        #         "company_name": company_name,
        #         "mobile_number": current_user.mobile_number,
        #         "profile_picture_url": current_user.profile_picture_url,
        #         "language_preference": current_user.language_preference,
        #         "timezone": current_user.timezone,
        #         "two_factor_enabled": current_user.two_factor_enabled
        #     }
        # }
    except Exception as e:
        logger.error(f"Error fetching current user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )

# =====================================================
# BULK OPERATIONS
# =====================================================
@router.post("/bulk-activate")
async def bulk_activate_users(
    request_data: dict,
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """Activate multiple users at once."""
    
    try:
        user_ids = request_data.get("user_ids", [])
        
        if not user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user IDs provided"
            )
        
        updated_count = db.query(User).filter(
            User.id.in_(user_ids)
        ).update(
            {
                "is_active": True,
                "updated_at": datetime.utcnow()
            },
            synchronize_session=False
        )
        
        db.commit()
        
        return {"message": f"Activated {updated_count} users successfully"}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk_activate_users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate users: {str(e)}"
        )

@router.post("/bulk-deactivate")
async def bulk_deactivate_users(
    request_data: dict,
    db: Session = Depends(get_db),
    # TEMPORARILY DISABLED FOR TESTING - UNCOMMENT WHEN READY:
    # current_user: User = Depends(get_current_user)
):
    """Deactivate multiple users at once."""
    
    try:
        user_ids = request_data.get("user_ids", [])
        
        if not user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user IDs provided"
            )
        
        updated_count = db.query(User).filter(
            User.id.in_(user_ids)
        ).update(
            {
                "is_active": False,
                "updated_at": datetime.utcnow()
            },
            synchronize_session=False
        )
        
        db.commit()
        
        return {"message": f"Deactivated {updated_count} users successfully"}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk_deactivate_users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate users: {str(e)}"
        )