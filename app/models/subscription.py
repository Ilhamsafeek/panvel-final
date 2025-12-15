from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Module(Base):
    __tablename__ = "modules"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    module_code = Column(String(50), unique=True, nullable=False, index=True)
    module_name = Column(String(255), nullable=False)
    module_description = Column(Text)
    icon = Column(String(100))
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    subscriptions = relationship("CompanyModuleSubscription", back_populates="module")
    pricing = relationship("ModulePricing", back_populates="module", cascade="all, delete-orphan")


class CompanyModuleSubscription(Base):
    __tablename__ = "company_module_subscriptions"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    module_code = Column(String(50), ForeignKey('modules.module_code'), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    subscribed_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="module_subscriptions")
    module = relationship("Module", back_populates="subscriptions")