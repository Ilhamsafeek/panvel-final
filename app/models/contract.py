# =====================================================
# FILE: app/models/contract.py
# Updated Contract Model - Fixed Foreign Key Issue
# =====================================================

from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text, Float, JSON, Numeric, Date
from datetime import datetime
from app.core.database import Base

class Contract(Base):
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    project_id = Column(Integer, nullable=True)
    
    contract_number = Column(String(100), unique=True, nullable=False, index=True)
    contract_title = Column(String(500), nullable=False)
    contract_title_ar = Column(String(500))
    contract_type = Column(String(100))
    profile_type = Column(String(50))
    contract_category = Column(String(100))  #  ADD
    template_id = Column(Integer, nullable=True)
    parent_contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True)
    
    # PARTY FIELDS
    party_a_name = Column(String(255))
    party_a_id = Column(Integer)
    party_b_name = Column(String(255))  # ← THIS IS THE KEY ONE
    party_b_id = Column(Integer)
    party_b_lead_id = Column(Integer)
    project_name = Column(String(255))  #  ADD
    
    # Financial
    contract_value = Column(Numeric(20, 2))
    currency = Column(String(10), default='QAR')
    
    # Dates
    start_date = Column(Date)
    end_date = Column(Date)
    signing_date = Column(Date)
    effective_date = Column(Date)
    expiry_date = Column(Date)
    renewal_date = Column(Date)
    signed_date = Column(Date)
    
    # Renewal
    auto_renewal = Column(Boolean, default=False)
    renewal_period_months = Column(Integer)
    renewal_notice_days = Column(Integer)
    
    # Status
    status = Column(String(50), default='draft')
    workflow_status = Column(String(50))
    approval_status = Column(String(50))  
    signature_status = Column(String(50))
    current_version = Column(Integer, default=1)
    
    # Locking
    is_locked = Column(Boolean, default=False)
    locked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    locked_at = Column(DateTime)
    
    # Legal/Compliance
    confidentiality_level = Column(String(50), default='STANDARD')
    language = Column(String(10), default='en')
    governing_law = Column(String(100))
    
    # Description fields
    description = Column(Text)  #  ADD
    description_ar = Column(Text)  #  ADD
    
    # Flags
    is_template = Column(Boolean, default=False)
    
    # Audit
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime)
    is_deleted = Column(Boolean, default=False)
    party_esignature_authority_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    counterparty_esignature_authority_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"))
    version_number = Column(Integer, nullable=False)
    version_type = Column(String(50))  # draft, internal_review, negotiation, final
    contract_content = Column(Text, nullable=False)  # FULL HTML/TEXT CONTENT
    contract_content_ar = Column(Text)  # Arabic version
    change_summary = Column(Text)
    is_major_version = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    

class ContractTemplate(Base):
    __tablename__ = "contract_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_name = Column(String(255), nullable=False)
    template_type = Column(String(100))
    template_category = Column(String(100))
    description = Column(Text)
    template_content = Column(Text)  #  ADDED: Store the actual content
    template_content_ar = Column(Text)  #  ADDED: Arabic content
    file_url = Column(Text)  # Legacy field for file-based templates
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    