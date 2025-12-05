# =====================================================
# FILE: app/core/subscription_guard.py
# Subscription-based Route Protection
# Internal users have full access, External users need subscriptions
# =====================================================

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.subscription_service import SubscriptionService

import logging

logger = logging.getLogger(__name__)


def require_module_subscription(module_code: str):
    """
    Dependency to check if user's company has subscription to specific module
    
    LOGIC:
    - Super admins: Always have access
    - Internal users: Always have access (they can't subscribe, but they have full system access)
    - External users: Must have company subscription
    
    Usage in routes:
    @app.get("/some-protected-route")
    async def protected_route(
        user: User = Depends(require_module_subscription("clm"))
    ):
        # Route logic here
        pass
    """
    async def check_subscription(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        """Check if user has access to the module"""
        try:
            # Super admins always have access
            if current_user.user_type == 'super_admin':
                logger.info(f"Super admin {current_user.email} accessing {module_code}")
                return current_user
            
            # Internal users always have access (they are staff/administrators)
            if current_user.user_type == 'internal':
                logger.info(f"Internal user {current_user.email} accessing {module_code}")
                return current_user
            
            # External users must have company and subscription
            if not current_user.company_id:
                logger.warning(f"User {current_user.email} has no company")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not associated with any company"
                )
            
            # Check subscription for external users
            has_access = SubscriptionService.has_module_access(
                current_user.company_id,
                module_code,
                db
            )
            
            if not has_access:
                logger.warning(
                    f"Company {current_user.company_id} has no subscription to {module_code}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Your company does not have access to the {module_code.upper()} module. Please subscribe to this module in User Settings."
                )
            
            logger.info(
                f"User {current_user.email} (Company: {current_user.company_id}) "
                f"accessed {module_code}"
            )
            return current_user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify module access"
            )
    
    return check_subscription


# Module code constants
class ModuleCodes:
    """Available module codes"""
    CLM = "clm"
    CORRESPONDENCE = "correspondence"
    RISK = "risk"
    OBLIGATIONS = "obligations"
    REPORTS = "reports"
    BLOCKCHAIN = "blockchain"
    EXPERT = "expert"


def get_user_accessible_modules(user: User, db: Session) -> list:
    """
    Get list of modules the user can access
    
    Returns:
        List of module codes the user has access to
    """
    try:
        # Super admins and internal users have access to all modules
        if user.user_type in ['super_admin', 'internal']:
            return [
                ModuleCodes.CLM,
                ModuleCodes.CORRESPONDENCE,
                ModuleCodes.RISK,
                ModuleCodes.OBLIGATIONS,
                ModuleCodes.REPORTS,
                ModuleCodes.BLOCKCHAIN,
                ModuleCodes.EXPERT
            ]
        
        # External users get modules based on company subscription
        if user.company_id:
            return SubscriptionService.get_company_subscriptions(user.company_id, db)
        
        return []
        
    except Exception as e:
        logger.error(f"Error getting accessible modules: {str(e)}")
        return []