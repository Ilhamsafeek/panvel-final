# =====================================================
# FILE: app/api/api_v1/users/license.py
# License & Module Subscription Management API
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, Company
from app.models.subscription import Module, CompanyModuleSubscription
from app.models.pricing import ModulePricing

logger = logging.getLogger(__name__)
router = APIRouter()


# =====================================================
# PYDANTIC MODELS
# =====================================================

class ModulePricingResponse(BaseModel):
    module_code: str
    module_name: str
    module_description: str
    icon: str
    price_monthly: float
    price_annual: float
    currency: str
    is_subscribed: bool


class LicenseUpdateRequest(BaseModel):
    license_type: str  # 'individual' or 'corporate'
    number_of_users: int


class ModuleSubscriptionRequest(BaseModel):
    module_code: str
    action: str  # 'subscribe' or 'unsubscribe'


# =====================================================
# GET MODULE PRICING BY LICENSE TYPE
# =====================================================

@router.get("/license/modules/pricing")
async def get_module_pricing(
    license_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all modules with pricing based on license type
    Returns pricing for Individual or Corporate licenses
    """
    try:
        # Get user's current license type if not specified
        if not license_type:
            company = db.query(Company).filter(Company.id == current_user.company_id).first()
            license_type = company.license_type if company and company.license_type else 'individual'
        
        # Validate license type
        if license_type not in ['individual', 'corporate']:
            license_type = 'individual'
        
        # Get all active modules with pricing
        modules_query = db.query(
            Module, ModulePricing
        ).join(
            ModulePricing,
            and_(
                Module.module_code == ModulePricing.module_code,
                ModulePricing.license_type == license_type,
                ModulePricing.is_active == True
            )
        ).filter(
            Module.is_active == True
        ).order_by(Module.display_order)
        
        modules_data = []
        
        # Get user's subscribed modules
        subscribed_modules = []
        if current_user.company_id:
            subscriptions = db.query(CompanyModuleSubscription.module_code).filter(
                and_(
                    CompanyModuleSubscription.company_id == current_user.company_id,
                    CompanyModuleSubscription.is_active == True
                )
            ).all()
            subscribed_modules = [sub.module_code for sub in subscriptions]
        
        # Build response
        for module, pricing in modules_query.all():
            modules_data.append({
                "module_code": module.module_code,
                "module_name": module.module_name,
                "module_description": module.module_description,
                "icon": module.icon,
                "price_monthly": float(pricing.price_monthly),
                "price_annual": float(pricing.price_annual),
                "currency": pricing.currency,
                "is_subscribed": module.module_code in subscribed_modules
            })
        
        return {
            "success": True,
            "license_type": license_type,
            "modules": modules_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching module pricing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch module pricing"
        )


# =====================================================
# GET CURRENT LICENSE INFO
# =====================================================

@router.get("/license/info")
async def get_license_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current license information for the user's company
    """
    try:
        if not current_user.company_id:
            return {
                "success": True,
                "license": {
                    "type": "individual",
                    "number_of_users": 1,
                    "max_contracts": 10,
                    "active_users": 1
                }
            }
        
        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        # Count active users
        active_users = db.query(User).filter(
            and_(
                User.company_id == current_user.company_id,
                User.is_active == True
            )
        ).count()
        
        # Determine max contracts based on license type
        license_type = company.license_type or 'individual'
        max_contracts = "Unlimited" if license_type == 'corporate' else "10"
        
        # Parse number of users
        number_of_users_str = str(company.number_of_users) if company.number_of_users else "1"
        if '-' in number_of_users_str:
            max_users = int(number_of_users_str.split('-')[-1])
        else:
            max_users = int(number_of_users_str)
        
        return {
            "success": True,
            "license": {
                "type": license_type,
                "number_of_users": number_of_users_str,
                "max_users": max_users,
                "max_contracts": max_contracts,
                "active_users": active_users,
                "expiry": company.subscription_expiry.isoformat() if company.subscription_expiry else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching license info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch license information"
        )


# =====================================================
# UPDATE LICENSE TYPE
# =====================================================

@router.put("/license/update")
async def update_license(
    data: LicenseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update company license type and number of users
    Only admin users can perform this action
    """
    try:
       
        if not current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No company associated with this user"
            )
        
        # Validate license type
        if data.license_type not in ['individual', 'corporate']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid license type. Must be 'individual' or 'corporate'"
            )
        
        # Validate number of users
        if data.number_of_users < 1 or data.number_of_users > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Number of users must be between 1 and 20"
            )
        
        # Get company
        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        # Store old license type for comparison
        old_license_type = company.license_type
        
        # Update company license
        company.license_type = data.license_type
        
        # Format number of users
        if data.number_of_users == 1:
            company.number_of_users = "1"
        elif data.number_of_users <= 5:
            company.number_of_users = str(data.number_of_users)
        elif data.number_of_users <= 10:
            company.number_of_users = "6-10"
        else:
            company.number_of_users = "11-20"
        
        company.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(company)
        
        logger.info(
            f"License updated for company {company.id}: "
            f"{old_license_type} -> {data.license_type}, "
            f"users: {company.number_of_users}"
        )
        
        return {
            "success": True,
            "message": "License updated successfully",
            "license": {
                "type": company.license_type,
                "number_of_users": company.number_of_users
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating license: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update license"
        )


# =====================================================
# MANAGE MODULE SUBSCRIPTION
# =====================================================

@router.post("/modules/subscription")
async def manage_module_subscription(
    data: ModuleSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Subscribe or unsubscribe from a module
    Any authenticated user can manage module subscriptions for their company
    """
    try:
        # Users can manage their own company's subscriptions
        # No admin restriction needed
        
        if not current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No company associated with this user"
            )
        
        # Validate module exists
        module = db.query(Module).filter(Module.module_code == data.module_code).first()
        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        # Check if subscription exists
        subscription = db.query(CompanyModuleSubscription).filter(
            and_(
                CompanyModuleSubscription.company_id == current_user.company_id,
                CompanyModuleSubscription.module_code == data.module_code
            )
        ).first()
        
        if data.action == "subscribe":
            if subscription:
                # Reactivate if exists
                subscription.is_active = True
                subscription.updated_at = datetime.utcnow()
                message = f"Reactivated subscription to {module.module_name}"
            else:
                # Create new subscription
                subscription = CompanyModuleSubscription(
                    company_id=current_user.company_id,
                    module_code=data.module_code,
                    is_active=True,
                    subscribed_date=datetime.utcnow()
                )
                db.add(subscription)
                message = f"Subscribed to {module.module_name}"
                
        elif data.action == "unsubscribe":
            if subscription:
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                message = f"Unsubscribed from {module.module_name}"
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subscription not found"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action. Must be 'subscribe' or 'unsubscribe'"
            )
        
        db.commit()
        
        logger.info(f"Module subscription updated: {message} for company {current_user.company_id}")
        
        return {
            "success": True,
            "message": message,
            "module_code": data.module_code,
            "is_subscribed": data.action == "subscribe"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error managing module subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to manage module subscription"
        )