# =====================================================
# FILE: app/models/pricing.py
# Module Pricing Model - FIXED VERSION
# =====================================================

from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class ModulePricing(Base):
    __tablename__ = "module_pricing"
    __table_args__ = (
        UniqueConstraint('module_code', 'license_type', name='unique_module_license'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    module_code = Column(String(50), ForeignKey('modules.module_code', ondelete='CASCADE'), nullable=False, index=True)
    license_type = Column(String(20), nullable=False, index=True)  # 'individual' or 'corporate'
    price_monthly = Column(Numeric(10, 2), nullable=False, default=0.00)
    price_annual = Column(Numeric(10, 2), nullable=False, default=0.00)
    currency = Column(String(10), default='QAR')
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    module = relationship("Module", back_populates="pricing")