# =====================================================
# FILE: app/services/subscription_service.py
# FIXED - Removed is_subscription_valid() call
# =====================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Optional
from datetime import datetime
import logging

from app.models.subscription import Module, CompanyModuleSubscription

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing module subscriptions"""
    
    @staticmethod
    def get_all_modules(db: Session) -> List[Dict]:
        """Get all available modules"""
        try:
            modules = db.query(Module).filter(
                Module.is_active == True
            ).order_by(Module.display_order).all()
            
            return [{
                "code": m.module_code,
                "name": m.module_name,
                "description": m.module_description,
                "icon": m.icon,
                "order": m.display_order
            } for m in modules]
            
        except Exception as e:
            logger.error(f"Error getting modules: {str(e)}")
            return []
    
    @staticmethod
    def get_company_subscriptions(company_id: int, db: Session) -> List[str]:
        """Get list of module codes that company is subscribed to"""
        try:
            subscriptions = db.query(CompanyModuleSubscription).filter(
                and_(
                    CompanyModuleSubscription.company_id == company_id,
                    CompanyModuleSubscription.is_active == True
                )
            ).all()
            
            # ✅ FIXED: Check validity inline instead of calling method
            active_codes = []
            for sub in subscriptions:
                # Check if subscription is valid (not expired)
                is_valid = True
                
                if not sub.is_active:
                    is_valid = False
                
                if sub.expiry_date and sub.expiry_date < datetime.utcnow():
                    is_valid = False
                
                if is_valid:
                    active_codes.append(sub.module_code)
            
            logger.info(f"Company {company_id} has {len(active_codes)} active subscriptions")
            return active_codes
            
        except Exception as e:
            logger.error(f"Error getting company subscriptions: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def has_module_access(company_id: int, module_code: str, db: Session) -> bool:
        """Check if company has access to specific module"""
        try:
            subscription = db.query(CompanyModuleSubscription).filter(
                and_(
                    CompanyModuleSubscription.company_id == company_id,
                    CompanyModuleSubscription.module_code == module_code,
                    CompanyModuleSubscription.is_active == True
                )
            ).first()
            
            if not subscription:
                return False
            
            # ✅ FIXED: Check validity inline
            if subscription.expiry_date and subscription.expiry_date < datetime.utcnow():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking module access: {str(e)}")
            return False
    
    @staticmethod
    def get_modules_with_access(company_id: int, db: Session) -> List[Dict]:
        """Get all modules with subscription status for company"""
        try:
            # Get all modules
            all_modules = SubscriptionService.get_all_modules(db)
            
            # Get company's active subscriptions
            subscribed_codes = SubscriptionService.get_company_subscriptions(company_id, db)
            
            # Mark which modules are subscribed
            for module in all_modules:
                module['subscribed'] = module['code'] in subscribed_codes
            
            return all_modules
            
        except Exception as e:
            logger.error(f"Error getting modules with access: {str(e)}")
            return []
    
    @staticmethod
    def subscribe_company_to_module(
        company_id: int, 
        module_code: str, 
        expiry_date: Optional[datetime],
        db: Session
    ) -> bool:
        """Subscribe company to a module"""
        try:
            # Check if subscription exists
            existing = db.query(CompanyModuleSubscription).filter(
                and_(
                    CompanyModuleSubscription.company_id == company_id,
                    CompanyModuleSubscription.module_code == module_code
                )
            ).first()
            
            if existing:
                # Update existing subscription
                existing.is_active = True
                existing.expiry_date = expiry_date
                existing.updated_at = datetime.utcnow()
            else:
                # Create new subscription
                new_sub = CompanyModuleSubscription(
                    company_id=company_id,
                    module_code=module_code,
                    is_active=True,
                    expiry_date=expiry_date,
                    subscribed_date=datetime.utcnow()
                )
                db.add(new_sub)
            
            db.commit()
            logger.info(f"Company {company_id} subscribed to {module_code}")
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing company to module: {str(e)}")
            db.rollback()
            return False
    
    @staticmethod
    def unsubscribe_company_from_module(
        company_id: int, 
        module_code: str, 
        db: Session
    ) -> bool:
        """Unsubscribe company from a module"""
        try:
            subscription = db.query(CompanyModuleSubscription).filter(
                and_(
                    CompanyModuleSubscription.company_id == company_id,
                    CompanyModuleSubscription.module_code == module_code
                )
            ).first()
            
            if subscription:
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Company {company_id} unsubscribed from {module_code}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error unsubscribing company from module: {str(e)}")
            db.rollback()
            return False