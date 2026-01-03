# =====================================================
# FILE: app/core/dependencies.py
# 🔧 FIXED - Cookie + JWT Authentication with Invalid Session Handling
# =====================================================

from fastapi import Depends, HTTPException, status, Request, Cookie, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
import logging

from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User

logger = logging.getLogger(__name__)

# Security scheme for API endpoints (optional for web routes)
security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session_token"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    🎯 FIXED Universal authentication dependency with invalid session handling
    - For web routes: Uses session token from cookie
    - For API routes: Uses Bearer token from Authorization header
    - Clears invalid cookies and redirects/returns error appropriately
    """
    token = None
    
    # Try session cookie first (for web pages)
    if session_token:
        token = session_token
        logger.debug(" Using session token from cookie")
    # Fall back to Bearer token (for API calls)
    elif credentials and credentials.credentials:
        token = credentials.credentials
        logger.debug(" Using Bearer token from Authorization header")
    
    if not token:
        # Check if this is a web request (looking for HTML response)
        accept_header = request.headers.get("accept", "")
        is_web_request = "text/html" in accept_header
        
        if is_web_request:
            logger.warning(f" Unauthorized web access to: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="Not authenticated",
                headers={"Location": "/login"}
            )
        else:
            logger.warning(f" Unauthorized API access to: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    # Verify token and user exists
    try:
        payload = verify_token(token)
        if not payload or not payload.get("sub"):
            raise ValueError("Invalid token payload")
        
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            # User from token doesn't exist in database
            logger.error(f" User ID {user_id} from token not found in database")
            
            # Clear the invalid cookie
            response.delete_cookie(
                key="session_token",
                httponly=True,
                secure=False,
                samesite="lax"
            )
            
            # Check if this is a web request
            accept_header = request.headers.get("accept", "")
            is_web_request = "text/html" in accept_header
            
            if is_web_request:
                raise HTTPException(
                    status_code=status.HTTP_303_SEE_OTHER,
                    detail="Your session is invalid. Please log in again.",
                    headers={"Location": "/login?error=invalid_session"}
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your session is invalid. Please log in again."
                )
        
        if not user.is_active:
            logger.warning(f" Inactive user attempted access: {user.email}")
            
            # Clear the cookie for inactive users
            response.delete_cookie(
                key="session_token",
                httponly=True,
                secure=False,
                samesite="lax"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active"
            )
        
        logger.debug(f" Authenticated user: {user.email} (ID: {user.id})")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Token verification failed: {str(e)}")
        
        # Clear potentially corrupted cookie
        response.delete_cookie(
            key="session_token",
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        # Check if this is a web request
        accept_header = request.headers.get("accept", "")
        is_web_request = "text/html" in accept_header
        
        if is_web_request:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="Authentication failed. Please log in again.",
                headers={"Location": "/login?error=auth_failed"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )


# =====================================================
# 🆕 OPTIONAL: Dependency for routes that DON'T require auth
# =====================================================
async def get_current_user_optional(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session_token"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[User]:
    """
    Optional authentication - returns None if not authenticated
    Use this for pages that work with or without auth (e.g., home page)
    """
    try:
        return await get_current_user(request, response, db, session_token, credentials)
    except HTTPException:
        return None


from app.middleware.rbac_middleware import get_user_roles
from app.core.permissions import Permission, has_permission

async def get_user_with_permissions(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session_token"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Get current user with their roles and permissions
    """
    # Get base user
    user = await get_current_user(request, response, db, session_token, credentials)
    
    # Get roles
    roles = get_user_roles(db, user.id)
    
    # Get all permissions
    all_permissions = set()
    for role in roles:
        from app.core.permissions import ROLE_PERMISSIONS
        all_permissions.update(ROLE_PERMISSIONS.get(role, set()))
    
    return {
        "user": user,
        "roles": roles,
        "permissions": [p.value for p in all_permissions],
        "is_super_admin": "Super Admin" in roles,
        "is_company_admin": "Company Admin" in roles
    }


def get_user_context(current_user: User, db: Session) -> dict:
    """
    Enhanced user context with roles and permissions
    """
    roles = get_user_roles(db, current_user.id)
    
    # Get company info
    company = None
    if current_user.company_id:
        from sqlalchemy import text
        result = db.execute(
            text("SELECT company_name FROM companies WHERE id = :id"),
            {"id": current_user.company_id}
        ).first()
        if result:
            company = result.company_name
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "full_name": f"{current_user.first_name} {current_user.last_name}",
        "company_id": current_user.company_id,
        "company_name": company,
        "roles": roles,
        "is_super_admin": "Super Admin" in roles,
        "is_company_admin": "Company Admin" in roles,
        "user_role": current_user.user_role,
        "department": current_user.department,
        "profile_picture": current_user.profile_picture_url
    }



from app.services.subscription_service import SubscriptionService

def get_user_context_with_subscriptions(current_user: User, db: Session) -> Dict:
    """
    Get user context with subscription information for templates
    """
    # Get basic user info
    user_context = {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "full_name": f"{current_user.first_name} {current_user.last_name}",
        "user_type": current_user.user_type,
        "company_id": current_user.company_id,
    }
    
    # Get subscriptions
    subscribed_modules = []
    is_internal = current_user.user_type == 'internal'
    
    if is_internal:
        # Internal users have access to all modules
        subscribed_modules = ['clm', 'correspondence', 'obligations', 'risk', 'reports', 'blockchain', 'expert']
    elif current_user.company_id:
        # External users - get their company subscriptions
        subscribed_modules = SubscriptionService.get_company_subscriptions(
            current_user.company_id,
            db
        )
    
    # Add subscription data to context
    user_context['subscriptions'] = subscribed_modules
    user_context['is_internal'] = is_internal
    
    # Helper function for templates - check if subscribed
    user_context['has_module'] = lambda module: module in subscribed_modules
    
    return user_context