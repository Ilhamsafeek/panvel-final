# =====================================================
# FILE: app/routers/subscription_router.py
# Subscription Management Routes - Excludes Internal Users
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.subscription_service import SubscriptionService

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


# =====================================================
# HELPER FUNCTION - Check if user can manage subscriptions
# =====================================================

def check_subscription_access(current_user: User):
    """
    Check if user can manage subscriptions.
    Internal users are not allowed to subscribe to modules.
    """
    if current_user.user_type == 'internal':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal users cannot manage module subscriptions. This feature is only available for external company users."
        )
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not associated with any company"
        )


# =====================================================
# PUBLIC ENDPOINTS (For External Users)
# =====================================================

@router.get("/modules")
async def get_available_modules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available modules with subscription status"""
    try:
        # Check access
        check_subscription_access(current_user)
        
        modules = SubscriptionService.get_modules_with_access(
            current_user.company_id,
            db
        )
        
        return {
            "success": True,
            "modules": modules,
            "company_id": current_user.company_id,
            "user_type": current_user.user_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get modules error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch modules"
        )


@router.get("/subscribed")
async def get_subscribed_modules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get modules the user's company is subscribed to"""
    try:
        # Check access
        check_subscription_access(current_user)
        
        subscribed_modules = SubscriptionService.get_company_subscriptions(
            current_user.company_id,
            db
        )
        
        return {
            "success": True,
            "subscribed_modules": subscribed_modules,
            "company_id": current_user.company_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get subscribed modules error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscribed modules"
        )


@router.post("/subscribe/{module_code}")
async def subscribe_to_module(
    module_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Subscribe current user's company to a module - EXTERNAL USERS ONLY"""
    try:
        # Check access - internal users cannot subscribe
        check_subscription_access(current_user)
        
        # Check if module exists
        available_modules = SubscriptionService.get_all_modules(db)
        module_codes = [m['code'] for m in available_modules]
        
        if module_code not in module_codes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_code}' not found"
            )
        
        # Subscribe the company
        success = SubscriptionService.subscribe_company_to_module(
            current_user.company_id,
            module_code,
            None,  # No expiry date for self-service subscriptions
            db
        )
        
        if success:
            logger.info(
                f"User {current_user.email} (type: {current_user.user_type}) subscribed company {current_user.company_id} "
                f"to module {module_code}"
            )
            return {
                "success": True,
                "message": f"Successfully subscribed to {module_code.upper()} module",
                "module_code": module_code,
                "company_id": current_user.company_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to subscribe to module. Please try again."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subscribe to module error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe to module"
        )


@router.delete("/unsubscribe/{module_code}")
async def unsubscribe_from_module(
    module_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unsubscribe current user's company from a module - EXTERNAL USERS ONLY"""
    try:
        # Check access - internal users cannot unsubscribe
        check_subscription_access(current_user)
        
        # Unsubscribe the company
        success = SubscriptionService.unsubscribe_company_from_module(
            current_user.company_id,
            module_code,
            db
        )
        
        if success:
            logger.info(
                f"User {current_user.email} (type: {current_user.user_type}) unsubscribed company {current_user.company_id} "
                f"from module {module_code}"
            )
            return {
                "success": True,
                "message": f"Successfully unsubscribed from {module_code.upper()} module",
                "module_code": module_code,
                "company_id": current_user.company_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to unsubscribe from module"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unsubscribe from module error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsubscribe from module"
        )


@router.get("/check/{module_code}")
async def check_module_access(
    module_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if current user's company has access to a specific module"""
    try:
        if not current_user.company_id:
            return {
                "success": True,
                "has_access": False,
                "module_code": module_code,
                "reason": "User not associated with any company"
            }
        
        # Super admins always have access
        if current_user.user_type == 'super_admin':
            return {
                "success": True,
                "has_access": True,
                "module_code": module_code,
                "reason": "Super admin access"
            }
        
        # Internal users have full access to all modules (they just can't subscribe)
        if current_user.user_type == 'internal':
            return {
                "success": True,
                "has_access": True,
                "module_code": module_code,
                "reason": "Internal user - full system access"
            }
        
        has_access = SubscriptionService.has_module_access(
            current_user.company_id,
            module_code,
            db
        )
        
        return {
            "success": True,
            "has_access": has_access,
            "module_code": module_code,
            "company_id": current_user.company_id
        }
        
    except Exception as e:
        logger.error(f"Check module access error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check module access"
        )


@router.get("/access-info")
async def get_subscription_access_info(
    current_user: User = Depends(get_current_user)
):
    """Check if current user can manage subscriptions"""
    can_manage = current_user.user_type != 'internal'
    
    return {
        "success": True,
        "can_manage_subscriptions": can_manage,
        "user_type": current_user.user_type,
        "reason": "Internal users cannot manage module subscriptions" if not can_manage else "User can manage subscriptions"
    }


# =====================================================
# ADMIN-ONLY ROUTES (For Managing Other Companies)
# =====================================================

@router.post("/admin/subscribe/{company_id}/{module_code}")
async def admin_subscribe_company(
    company_id: int,
    module_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin-only: Subscribe any company to a module"""
    try:
        # Admin check
        if current_user.user_type not in ['super_admin', 'company_admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can manage other companies' subscriptions"
            )
        
        success = SubscriptionService.subscribe_company_to_module(
            company_id,
            module_code,
            None,
            db
        )
        
        if success:
            return {
                "success": True,
                "message": f"Successfully subscribed company {company_id} to {module_code}",
                "module_code": module_code,
                "company_id": company_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to subscribe company to module"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin subscribe error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe company to module"
        )


@router.delete("/admin/unsubscribe/{company_id}/{module_code}")
async def admin_unsubscribe_company(
    company_id: int,
    module_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin-only: Unsubscribe any company from a module"""
    try:
        # Admin check
        if current_user.user_type not in ['super_admin', 'company_admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can manage other companies' subscriptions"
            )
        
        success = SubscriptionService.unsubscribe_company_from_module(
            company_id,
            module_code,
            db
        )
        
        if success:
            return {
                "success": True,
                "message": f"Successfully unsubscribed company {company_id} from {module_code}",
                "module_code": module_code,
                "company_id": company_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to unsubscribe company from module"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin unsubscribe error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsubscribe company from module"
        )