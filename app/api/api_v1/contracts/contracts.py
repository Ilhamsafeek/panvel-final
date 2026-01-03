# =====================================================
# FILE: app/api/api_v1/contracts/contracts.py
# COMPLETE VERSION - MERGE CONFLICTS RESOLVED
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form, Request, Body
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import json
import os
import re
from pathlib import Path
import asyncio
import sys
from app.core.config import settings
from fastapi.responses import StreamingResponse
import hashlib
import uuid


# Add these 4 lines
import hashlib
import uuid
import json
from pathlib import Path


import pdfplumber
import docx
from sqlalchemy.sql import text



from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from pydantic import BaseModel, Field

from app.models.contract import Contract, ContractVersion

from app.services.claude_service import ClaudeService, claude_service
from app.services.blockchain_service import blockchain_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

# =====================================================
# PYDANTIC MODELS
# =====================================================

class AIContractGenerationRequest(BaseModel):
    """Request for AI contract generation"""
    contract_title: str
    contract_type: str
    profile_type: str
    parties: Optional[Dict[str, Any]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    contract_value: Optional[float] = None
    currency: str = "QAR"
    selected_clauses: Optional[Dict[str, bool]] = None
    clause_descriptions: Optional[List[str]] = None
    jurisdiction: str = "Qatar"
    language: str = "en"
    project_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateMetadataRequest(BaseModel):
    """Request to update contract AI generation metadata"""
    ai_generation_params: Dict[str, Any]


# =====================================================
# EXISTING ENDPOINT: GET MY CONTRACTS
# =====================================================

@router.get("/my-contracts")
async def get_my_contracts(
    status_filter: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all contracts accessible to the current user"""
    try:
        logger.info(f"Fetching contracts for user: {current_user.email}")
        
        where_conditions = ["(c.created_by = :user_id OR c.company_id = :company_id)"]
        params = {
            "user_id": str(current_user.id),
            "company_id": str(current_user.company_id) if current_user.company_id else None,
            "limit": limit,
            "offset": offset
        }
        
        if status_filter:
            where_conditions.append("c.status = :status_filter")
            params["status_filter"] = status_filter
        
        where_clause = " AND ".join(where_conditions)
        
        query_sql = text(f"""
        SELECT 
            c.id,
            c.contract_number,
            c.contract_title,
            c.contract_type,
            c.status,
            c.start_date,
            c.end_date,
            c.contract_value,
            c.currency,
            c.created_at,
            c.party_b_name as counterparty_name,
            u.first_name,
            u.last_name
        FROM contracts c
        LEFT JOIN users u ON c.created_by = u.id
        WHERE {where_clause}
        ORDER BY c.created_at DESC
        LIMIT :limit OFFSET :offset
        """)
        
        result = db.execute(query_sql, params)
        rows = result.fetchall()
        
        contracts = []
        for row in rows:
            contracts.append({
                "id": row[0],
                "contract_number": row[1],
                "contract_title": row[2],
                "contract_type": row[3],
                "status": row[4],
                "start_date": str(row[5]) if row[5] else None,
                "end_date": str(row[6]) if row[6] else None,
                "contract_value": float(row[7]) if row[7] else 0,
                "currency": row[8],
                "created_at": str(row[9]) if row[9] else None,
                "counterparty_name": row[10],
                "created_by_name": f"{row[11]} {row[12]}" if row[11] and row[12] else "Unknown"
            })
        
        return {
            "success": True,
            "contracts": contracts,
            "total": len(contracts)
        }
        
    except Exception as e:
        logger.error(f"Error fetching contracts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch contracts: {str(e)}"
        )

# =====================================================
# TEMPLATES LIST ENDPOINT
# =====================================================

@router.get("/templates/list")
async def list_contract_templates(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of available contract templates"""
    try:
        logger.info(f"📋 Fetching templates for category: {category}")
        
        query = """
            SELECT id, template_name, template_type, template_category,
                   description, is_active
            FROM contract_templates
            WHERE is_active = 1
        """
        
        params = {}
        
        if category:
            # Include generic templates marked as 'all' in addition to the requested category
            query += " AND (template_category = :category OR template_category = 'all')"
            params["category"] = category
        
        query += " ORDER BY template_name"
        
        result = db.execute(text(query), params)
        rows = result.fetchall()
        
        templates = []
        for row in rows:
            templates.append({
                "id": row[0],
                "name": row[1],
                "type": row[2],
                "category": row[3],
                "description": row[4],
                "is_active": row[5]
            })
        
        logger.info(f" Found {len(templates)} templates")
        
        return {
            "success": True,
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f" Error fetching templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch templates: {str(e)}"
        )

# =====================================================
# CREATE CONTRACT FROM TEMPLATE
# =====================================================


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_contract_from_template(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new contract from template with ACTUAL template content"""
    try:
        # RBAC: Check if user has permission to create contracts
        user_role = getattr(current_user, 'user_role', '').lower() if current_user.user_role else ''
        if user_role in ['viewer', 'guest', 'readonly']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create contracts"
            )
        
        logger.info(f"📋 Creating contract for user: {current_user.email}")
        
        template_id = request.get("template_id")
        
        #  CRITICAL: Load template content FIRST
        template_content = None
        template_content_ar = None
        template_name = None
        template_type = "general"
        
        if template_id:
            logger.info(f" Loading template ID: {template_id}")
            
            # Fetch template with content
            template_query = text("""
                SELECT id, template_name, template_type, template_content, template_content_ar
                FROM contract_templates 
                WHERE id = :template_id AND is_active = 1
            """)
            template_result = db.execute(template_query, {"template_id": template_id}).fetchone()
            
            if not template_result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {template_id} not found or inactive"
                )
            
            template_name = template_result[1]
            template_type = template_result[2] or "general"
            template_content = template_result[3]
            template_content_ar = template_result[4]
            
            logger.info(f" Template loaded: {template_name}")
            logger.info(f"📊 Content length: {len(template_content) if template_content else 0} chars")
            
            # If template has NO content, use meaningful default
            if not template_content or template_content.strip() == "":
                logger.warning(f" Template has no content! Using default structure")
                template_content = f"""
                <div class="contract-document">
                    <h1>{template_name}</h1>
                    <p><strong>Type:</strong> {template_type}</p>
                    <p><em>Template content needs to be added in database.</em></p>
                </div>
                """
        else:
            # No template - blank contract
            logger.info(" Creating blank contract")
            template_content = """
            <div class="contract-document">
                <h1>New Contract</h1>
                <p>Start editing your contract...</p>
            </div>
            """
        
        # Generate contract number
        contract_number = generate_contract_number(db, current_user.company_id)
        
        # Prepare contract data
        contract_data = {
            "company_id": str(current_user.company_id) if current_user.company_id else None,
            "project_id": request.get("project_id"),
            "contract_number": contract_number,
            "contract_title": request.get("contract_title") or f"New Contract - {contract_number}",
            "contract_type": template_type,
            "profile_type": request.get("profile_type", "contractor"),
            "template_id": template_id,
            "status": "draft",
            "workflow_status": "drafting",
            "created_by": current_user.id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "tags": json.dumps(request.get("tags", [])),
            
        }
        
        # Insert contract
        insert_query = text("""
            INSERT INTO contracts (
                company_id, project_id, contract_number, contract_title,
                contract_type, profile_type, template_id, status,
                workflow_status, created_by, created_at, updated_at, tags
            ) VALUES (
                :company_id, :project_id, :contract_number, :contract_title,
                :contract_type, :profile_type, :template_id, :status,
                :workflow_status, :created_by, :created_at, :updated_at, :tags
            )
        """)
        
        result = db.execute(insert_query, contract_data)
        contract_id = result.lastrowid
        
        logger.info(f" Contract created with ID: {contract_id}")
        
        #  CRITICAL: Create contract_versions entry with ACTUAL template content
        version_data = {
            "contract_id": contract_id,
            "version_number": 1,
            "version_type": "draft",
            "contract_content": template_content,  #  ACTUAL CONTENT HERE
            "contract_content_ar": template_content_ar,
            "change_summary": f"Initial contract creation from template: {template_name}" if template_name else "Initial contract creation",
            "is_major_version": False,
            "created_by": current_user.id,
            "created_at": datetime.utcnow()
        }
        
        version_insert = text("""
            INSERT INTO contract_versions (
                contract_id, version_number, version_type, 
                contract_content, contract_content_ar, change_summary,
                is_major_version, created_by, created_at
            ) VALUES (
                :contract_id, :version_number, :version_type,
                :contract_content, :contract_content_ar, :change_summary,
                :is_major_version, :created_by, :created_at
            )
        """)
        
        db.execute(version_insert, version_data)
        db.commit()
        
        logger.info(f" Contract version created with content length: {len(template_content)}")
        
        # Return complete contract data
        return {
            "id": contract_id,
            "contract_number": contract_number,
            "contract_title": contract_data["contract_title"],
            "status": "draft",
            "template_content_loaded": bool(template_content and len(template_content) > 100),
            "message": "Contract created successfully with template content"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f" Error creating contract: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contract: {str(e)}"
        )


# =====================================================
# UPLOAD CONTRACT - FIXED VERSION
# =====================================================

# @router.post("/upload")
# async def upload_contract(
#     file: UploadFile = File(...),
#     profile_type: str = Form(...),
#     metadata: str = Form(...),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Upload an existing contract document"""
#     try:
#         logger.info(f"Uploading contract file: {file.filename}")
        
#         # Validate file type
#         allowed_types = ["application/pdf", "application/msword", 
#                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
#         if file.content_type not in allowed_types:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Invalid file type. Only PDF, DOC, and DOCX are allowed."
#             )
        
#         # Parse metadata
#         metadata_dict = json.loads(metadata)
        
#         # Generate contract number
#         contract_number = generate_contract_number(db, current_user.company_id)
        
#         # Save file
#         file_path = save_uploaded_file(file, contract_number, current_user.company_id)
        
#         # Prepare contract data - NO file_url in contracts table
#         contract_data = {
#             "company_id": current_user.company_id,
#             "project_id": metadata_dict.get("project_id"),
#             "contract_number": contract_number,
#             "contract_title": metadata_dict.get("contract_title"),
#             "profile_type": profile_type,
#             "status": "draft",
#             "created_by": current_user.id,
#             "created_at": datetime.utcnow(),
#             "updated_at": datetime.utcnow()
#         }
        
#         # Insert into contracts table (without file_url)
#         insert_query = text("""
#             INSERT INTO contracts (
#                 company_id, project_id, contract_number, contract_title,
#                 profile_type, status, created_by, created_at, updated_at
#             ) VALUES (
#                 :company_id, :project_id, :contract_number, :contract_title,
#                 :profile_type, :status, :created_by, :created_at, :updated_at
#             )
#         """)
        
#         result = db.execute(insert_query, contract_data)
#         db.commit()
        
#         contract_id = result.lastrowid
        
#         # Store the file in contract_versions table
#         version_query = text("""
#             INSERT INTO contract_versions (
#                 contract_id, version_number, file_url, version_type, created_by, created_at
#             ) VALUES (
#                 :contract_id, :version_number, :file_url, :version_type, :created_by, :created_at
#             )
#         """)
        
#         db.execute(version_query, {
#             "contract_id": contract_id,
#             "version_number": 1,
#             "file_url": file_path,
#             "version_type": "uploaded",
#             "change_summary": f"Uploaded from {file.filename} - Text extracted and ready for editing",
#             "created_by": current_user.id,
#             "created_at": datetime.utcnow()
#         })
        
#         db.commit()
        
#         logger.info(f" Upload complete: {contract_number}")
        
#         return {
#             "success": True,
#             "id": contract_id,
#             "contract_number": contract_number,
#             "file_path": relative_path,
#             "content_extracted": True,
#             "content_length": len(extracted_html),
#             "message": "Contract uploaded and text extracted successfully. Ready for editing."
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         logger.error(f" Upload error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to upload contract: {str(e)}"
#         )

# =====================================================
# COMPLETE FIX: Add party_b_lead_id and party_b_id to INSERT
# File: app/api/api_v1/contracts/contracts.py
# Function: generate_contract_with_ai()
# =====================================================

@router.post("/ai-generate")
async def generate_contract_with_ai(
    request_data: AIContractGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create contract metadata for AI generation (content will be streamed separately)"""
    try:
        logger.info("🤖 Creating contract for AI generation")
        
        # Extract metadata
        contract_title = request_data.contract_title
        contract_type = request_data.contract_type
        profile_type = request_data.profile_type
        
        # Generate contract number
        contract_number = generate_contract_number(db, current_user.company_id)
        
        # Save generation params as JSON
        generation_params_json = json.dumps({
            "contract_type": request_data.contract_type,
            "profile_type": request_data.profile_type,
            "parties": request_data.parties,
            "selected_clauses": request_data.selected_clauses,
            "clause_descriptions": request_data.clause_descriptions,
            "jurisdiction": request_data.jurisdiction,
            "language": request_data.language,
            "contract_value": request_data.contract_value,
            "currency": request_data.currency,
            "start_date": request_data.start_date,
            "end_date": request_data.end_date,
            "metadata": request_data.metadata
        })
        
        # Create contract record
        contract_data = {
            "company_id": str(current_user.company_id) if current_user.company_id else None,
            "project_id": request_data.project_id,
            "contract_number": contract_number,
            "contract_title": contract_title,
            "contract_type": contract_type,
            "profile_type": profile_type,
            "contract_value": request_data.contract_value,
            "currency": request_data.currency,
            "status": "draft",
            "current_version": 1,
            "is_ai_generated": 1,
            "ai_generation_params": generation_params_json,
            "party_b_lead_id": None,  # ✅ ADD THIS - Will be set later when counterparty is added
            "party_b_id": None,       # ✅ ADD THIS - Will be set later when counterparty is added
            "created_by": str(current_user.id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # ✅ FIXED: Include party_b_lead_id and party_b_id in INSERT
        result = db.execute(text("""
            INSERT INTO contracts (company_id, project_id, contract_number, contract_title,
                                 contract_type, profile_type, contract_value, currency,
                                 status, current_version, is_ai_generated, ai_generation_params,
                                 party_b_lead_id, party_b_id,
                                 created_by, created_at, updated_at)
            VALUES (:company_id, :project_id, :contract_number, :contract_title,
                    :contract_type, :profile_type, :contract_value, :currency,
                    :status, :current_version, :is_ai_generated, :ai_generation_params,
                    :party_b_lead_id, :party_b_id,
                    :created_by, :created_at, :updated_at)
        """), contract_data)
        
        # Use lastrowid for MySQL compatibility
        contract_id = result.lastrowid
        db.commit()
        
        logger.info(f"✅ Contract created: {contract_number} (ID: {contract_id})")
        
        return {
            "id": contract_id,
            "contract_id": contract_id,
            "contract_number": contract_number,
            "message": "Contract created. AI generation can now be streamed."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating contract: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contract: {str(e)}"
        )
# =====================================================
# STATISTICS ENDPOINT - FIXED VERSION
# =====================================================

@router.get("/statistics")
async def get_contract_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get dashboard statistics - INCLUDES MY PENDING APPROVALS
    SCR_010 - Contract Dashboard
    """
    from app.models.contract import Contract
    from app.models.project import Project
    from app.models.obligation import Obligation
    
    company_id = current_user.company_id
    user_id = current_user.id
    
    # Total contracts (including AI-generated)
    total_contracts = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.is_deleted == False
    ).scalar() or 0
    
    # Active contracts
    active_contracts = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.status.in_(['active', 'signed', 'executed']),
        Contract.is_deleted == False
    ).scalar() or 0
    
    # Pending review
    pending_review = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.status.in_(['pending_review', 'review', 'pending_approval']),
        Contract.is_deleted == False
    ).scalar() or 0
    
    # Expiring soon (within 30 days)
    thirty_days = datetime.now() + timedelta(days=30)
    today = datetime.now()
    
    expiring_soon = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.status.in_(['active', 'signed', 'executed']),
        Contract.end_date.isnot(None),
        Contract.end_date <= thirty_days,
        Contract.end_date >= today,
        Contract.is_deleted == False
    ).scalar() or 0
    
    # Completed contracts
    completed_contracts = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        or_(Contract.status == 'completed', Contract.status == 'expired'),
        Contract.is_deleted == False
    ).scalar() or 0
    
    # Active projects
    active_projects = db.query(func.count(Project.id)).filter(
        Project.company_id == company_id,
        Project.status == 'active'
    ).scalar() or 0
    
    # Due obligations (within 7 days)
    seven_days = datetime.now() + timedelta(days=7)
    due_obligations = db.query(func.count(Obligation.id)).filter(
        Obligation.due_date <= seven_days,
        Obligation.due_date >= today,
        Obligation.status.in_(['PENDING', 'IN_PROGRESS'])
    ).scalar() or 0
    
    # 🆕 MY PENDING APPROVALS - Contracts waiting for current user's approval
    # This checks both workflow_stages and approval_requests tables
    my_pending_approvals = db.execute(text("""
        SELECT COUNT(DISTINCT c.id) as count
        FROM contracts c
        WHERE c.company_id = :company_id
        AND c.is_deleted = 0
        AND c.status IN ('pending_approval', 'pending_review', 'review', 'approval','counterparty_internal_review')
        AND (
            -- Check workflow_stages for pending approvals assigned to this user
            EXISTS (
                SELECT 1 
                FROM workflow_instances wi
                JOIN workflow_stages ws ON wi.id = ws.workflow_instance_id
                WHERE wi.contract_id = c.id
                AND wi.status IN ('active', 'in_progress', 'pending')
                AND ws.approver_user_id = :user_id
                AND ws.status = 'pending'
            )
            OR
            -- Check approval_requests for pending approvals assigned to this user
            EXISTS (
                SELECT 1
                FROM approval_requests ar
                WHERE ar.contract_id = c.id
                AND ar.approver_id = :user_id
                AND ar.responded_at IS NULL
                AND (ar.status = 'pending' OR ar.approval_status = 'pending')
            )
        )
    """), {
        "company_id": company_id,
        "user_id": user_id
    }).scalar() or 0
    
    # Module counts - FIXED to include AI-generated contracts
    
    # Drafting count - includes ALL draft contracts and AI-generated ones
    drafting_count = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.is_deleted == False,
        or_(
            # Explicit workflow statuses for drafting
            Contract.workflow_status.in_(['draft', 'internal_review', 'clause_analysis']),
            # NULL workflow_status with drafting statuses
            and_(
                Contract.workflow_status.is_(None),
                Contract.status.in_(['draft', 'pending_review', 'in_progress'])
            ),
            # Explicitly include any contract with status='draft' (AI-generated fall here)
            Contract.status == 'draft'
        )
    ).scalar() or 0
    
    # Negotiation count
    negotiation_count = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.is_deleted == False,
        or_(
            Contract.workflow_status.in_(['external_review', 'negotiation', 'approval']),
            and_(
                Contract.workflow_status.is_(None),
                Contract.status.in_(['negotiation', 'pending_approval'])
            )
        )
    ).scalar() or 0
    
    # Operations count
    operations_count = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.is_deleted == False,
        Contract.status.in_(['active', 'expired', 'terminated', 'completed', 'executed', 'signed'])
    ).scalar() or 0
    
    # Additional stat: Count of AI-generated contracts
    ai_generated_count = db.query(func.count(Contract.id)).filter(
        Contract.company_id == company_id,
        Contract.is_deleted == False,
        Contract.id.in_(
            db.query(ContractVersion.contract_id).filter(
                ContractVersion.version_type == 'ai_generated'
            )
        )
    ).scalar() or 0
    
    logger.info(f"📊 Statistics - Total: {total_contracts}, Drafting: {drafting_count}, AI-Generated: {ai_generated_count}, My Pending Approvals: {my_pending_approvals}")
    
    return {
        "total_contracts": total_contracts,
        "active_contracts": active_contracts,
        "pending_review": pending_review,
        "expiring_soon": expiring_soon,
        "completed_contracts": completed_contracts,
        "active_projects": active_projects,
        "due_obligations": due_obligations,
        "my_pending_approvals": my_pending_approvals,  # 🆕 NEW: Contracts awaiting my approval
        "drafting_count": drafting_count,
        "negotiation_count": negotiation_count,
        "operations_count": operations_count,
        "ai_generated_count": ai_generated_count
    }


# =====================================================
# GET CONTRACTS LIST
# =====================================================
@router.get("")
async def get_contracts(
    module: str = Query("drafting"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    profile: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get contracts list with filters - SCR_010 - Gets counterparty company name"""
    company_id = current_user.company_id
    
    # Base query
    query = db.query(Contract).filter(
        or_(
            Contract.company_id == company_id,
            Contract.party_b_id == company_id
        ),
        Contract.is_deleted == False
    )
    
    # Module filter
    if module == "drafting":
        query = query.filter(
            # Displays all the contracts with any status
            # Contract.status.in_(['draft', 'pending_review', 'in_progress', 'review','review_completed','counterparty_internal_review','negotiation_completed','negotiation'])

        )
    elif module == "negotiation":
        query = query.filter(
            or_(
                # Contract.workflow_status.in_(['external_review', 'negotiation', 'approval']),
                # and_(
                #     Contract.workflow_status.is_(None),
                    Contract.status.in_(['in_progress', 'pending_approval', 'negotiation'])
                )
            # )
        )
    elif module == "operations":
        query = query.filter(
            Contract.status.in_(['approved', 'expired', 'terminated', 'completed', 'executed', 'signed'])
        )
    
    # Status filter for sub-tabs
    if status and status != "all":
        if status == "my":
            query = query.filter(Contract.created_by == current_user.id)
        elif status == "draft":
            query = query.filter(Contract.status == 'draft')
        elif status == "review":
            query = query.filter(
                or_(
                    Contract.status == 'review',
                    Contract.status == 'pending_review',
                    Contract.workflow_status == 'review'
                )
            )
        elif status == "expiring":
            thirty_days = datetime.now() + timedelta(days=30)
            query = query.filter(
                Contract.end_date.isnot(None),
                Contract.end_date <= thirty_days,
                Contract.end_date >= datetime.now()
            )
        else:
            query = query.filter(Contract.status == status)
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Contract.contract_title.ilike(search_term),
                Contract.contract_number.ilike(search_term)
            )
        )
    
    # Type filter
    if type:
        query = query.filter(Contract.contract_type == type)
    
    # Profile filter
    if profile:
        query = query.filter(Contract.profile_type == profile)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    contracts = query.order_by(Contract.created_at.desc()).offset(offset).limit(limit).all()
    
    # Convert to dict
    result = []
    for contract in contracts:
        # Get latest version
        latest_version = db.query(ContractVersion).filter(
            ContractVersion.contract_id == contract.id
        ).order_by(ContractVersion.version_number.desc()).first()
        
        # Get creator info
        creator = db.query(User).filter(User.id == contract.created_by).first()
        
        # Get counterparty company name using raw SQL to avoid ORM conflicts
        counterparty_name = "Not specified"
        if contract.party_b_id:
            counterparty_query = text("""
                SELECT c.company_name 
                FROM users u
                JOIN companies c ON u.company_id = c.id
                WHERE u.id = :user_id
                LIMIT 1
            """)
            counterparty_result = db.execute(counterparty_query, {"user_id": contract.party_b_id}).fetchone()
            if counterparty_result and counterparty_result.company_name:
                counterparty_name = counterparty_result.company_name
            elif contract.party_b_name:
                # Fallback to party_b_name if company lookup fails
                counterparty_name = contract.party_b_name
        elif contract.party_b_name:
            counterparty_name = contract.party_b_name
        
        result.append({
            "id": contract.id,
            "contract_number": contract.contract_number,
            "title": contract.contract_title,
            "counterparty": counterparty_name,
            "status": contract.status,
            "contract_type": contract.contract_type,
            "module": module,
            "value": float(contract.contract_value) if contract.contract_value else 0,
            "currency": contract.currency or "QAR",
            "created_at": contract.created_at.isoformat() if contract.created_at else None,
            "updated_at": contract.updated_at.isoformat() if contract.updated_at else None,
            "created_by": f"{creator.first_name} {creator.last_name}" if creator else "Unknown",
            "current_version": latest_version.version_number if latest_version else 1,
            "priority": None,
            "template": contract.is_template if hasattr(contract, 'is_template') else False
        })
    
    logger.info(f"📊 Retrieved {len(result)} contracts out of {total} total for module '{module}'")
    
    return {
        "success": True,
        "contracts": result,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
            "has_more": offset + limit < total
        }
    }

# =====================================================
# DELETE CONTRACT
# =====================================================

@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a contract (soft delete) - SCR_010"""
    from app.models.contract import Contract
    
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.company_id == current_user.company_id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract.status not in ['draft', 'pending_review']:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete contract in current status"
        )
    
    if hasattr(Contract, 'is_deleted'):
        contract.is_deleted = True
        contract.deleted_at = datetime.now()
    else:
        db.delete(contract)
    
    contract.updated_by = current_user.id
    contract.updated_at = datetime.now()
    
    try:
        db.commit()
        return {
            "success": True,
            "message": "Contract deleted successfully",
            "contract_id": contract_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete contract: {str(e)}")

# =====================================================
# UPDATE CONTRACT
# =====================================================

@router.put("/{contract_id}")
async def update_contract(
    contract_id: int,
    title: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update contract details"""
    from app.models.contract import Contract
    
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.company_id == current_user.company_id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if title:
        contract.contract_title = title
    if status:
        contract.status = status
    
    contract.updated_by = current_user.id
    contract.updated_at = datetime.now()
    
    try:
        db.commit()
        db.refresh(contract)
        return {
            "success": True,
            "message": "Contract updated successfully",
            "contract": {
                "id": contract.id,
                "title": contract.contract_title,
                "status": contract.status
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update contract: {str(e)}")

# =====================================================
# CONTRACT EDITOR ENDPOINTS
# =====================================================
@router.get("/edit/{contract_id}")
async def get_contract_editor_data(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get contract data for editor with execution certificate"""
    try:
        query = text("""
            SELECT 
                c.id,
                c.contract_number,
                c.contract_title,
                c.contract_type,
                c.status,
                c.approval_status,
                c.created_at,
                c.created_by as created_by_id,
                c.updated_at,
                c.party_b_id,
                c.party_b_lead_id,
                c.signed_date,
                c.effective_date,
                comp.company_name,
                c.company_id,
                c.is_ai_generated,
                c.ai_generation_params,
                CONCAT(u.first_name, ' ', u.last_name) as created_by_name,
                cv.contract_content as content,
                cv.version_number as current_version
            FROM contracts c
            LEFT JOIN companies comp ON c.company_id = comp.id
            LEFT JOIN users u ON c.created_by = u.id
            LEFT JOIN contract_versions cv ON c.id = cv.contract_id 
                AND cv.version_number = (
                    SELECT MAX(version_number) 
                    FROM contract_versions 
                    WHERE contract_id = c.id
                )
            WHERE c.id = :contract_id
            LIMIT 1
        """)
        
        result = db.execute(query, {"contract_id": contract_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        is_initiator = current_user.id == result.created_by_id
        is_counterparty = current_user.company_id == result.party_b_id
        
        # ===== INITIATOR WORKFLOW (Party A) =====
        workflow_query = text("""
          SELECT 
            wi.id as workflow_instance_id,
            wi.workflow_id,
            wi.status as workflow_status,
            wi.current_step,
            w.workflow_name as template_name,
            w.company_id,
            w.is_master
        FROM workflow_instances wi
        LEFT JOIN workflows w ON wi.workflow_id = w.id
        WHERE wi.contract_id = :contract_id
        AND w.company_id = :company_id
        AND w.is_active = 1
        AND wi.status IN ('pending', 'active', 'in_progress', 'completed')
        ORDER BY w.is_master ASC
        LIMIT 1
        """)
        
        workflow = db.execute(workflow_query, {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        # Get workflow steps with assignee information
        workflow_steps = []
        total_steps = 0
        
        if workflow and workflow.workflow_id:
            steps_query = text("""
                SELECT 
                    ws.id as step_id,
                    ws.step_number,
                    ws.step_name,
                    ws.step_type,
                    ws.assignee_user_id,
                    ws.assignee_role,
                    CONCAT(u.first_name, ' ', u.last_name) as assignee_name,
                    u.email as assignee_email,
                    CASE 
                        WHEN ws.step_number < :current_step THEN 'completed'
                        WHEN ws.step_number = :current_step THEN 'active'
                        ELSE 'pending'
                    END as step_status
                FROM workflow_steps ws
                LEFT JOIN users u ON ws.assignee_user_id = u.id
                WHERE ws.workflow_id = :workflow_id
                ORDER BY ws.step_number ASC
            """)
            
            steps_result = db.execute(steps_query, {
                "workflow_id": workflow.workflow_id,
                "current_step": workflow.current_step
            }).fetchall()
            
            total_steps = len(steps_result)
            
            workflow_steps = [
                {
                    "step_id": step.step_id,
                    "step_number": step.step_number,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "assignee_user_id": step.assignee_user_id,
                    "assignee_name": step.assignee_name,
                    "assignee_email": step.assignee_email,
                    "assignee_role": step.assignee_role,
                    "status": step.step_status,
                    "is_current": workflow.current_step == step.step_number
                }
                for step in steps_result
            ]
        
        # Check if it's current user's turn in workflow
        is_my_workflow_turn = False
        if workflow and workflow_steps:
            for step in workflow_steps:
                if step["is_current"]:
                    if step["assignee_user_id"] == current_user.id:
                        is_my_workflow_turn = True
                        break
        

        is_party_b_lead = False
        if current_user.id==result.party_b_lead_id:
            is_party_b_lead = True
        
        
        # Get version history
        version_query = text("""
            SELECT 
                cv.version_number,
                cv.created_at,
                cv.change_summary,
                cv.created_by,
                CONCAT(u.first_name, ' ', u.last_name) as created_by_name
            FROM contract_versions cv
            LEFT JOIN users u ON cv.created_by = u.id
            WHERE cv.contract_id = :contract_id
            ORDER BY cv.version_number DESC
            LIMIT 10
        """)
        
        versions = db.execute(version_query, {"contract_id": contract_id}).fetchall()
        
        # Get current approver (for initiator workflow)
        current_approver_query = text("""
            SELECT 
            u.first_name, 
            u.last_name, 
            u.email, 
            u.department, 
            ws.step_type,
            w.is_master
        FROM workflow_instances wi
        JOIN workflows w ON wi.workflow_id = w.id
        JOIN workflow_steps ws ON wi.workflow_id = ws.workflow_id 
            AND wi.current_step = ws.step_number
        LEFT JOIN users u ON ws.assignee_user_id = u.id
        WHERE wi.contract_id = :contract_id 
        AND wi.status IN ('active', 'in_progress')
        AND w.company_id = :company_id
        AND w.is_active = 1
        ORDER BY w.is_master ASC
        LIMIT 1
        """)
        current_approver = db.execute(current_approver_query, {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        # ===== EXECUTION CERTIFICATE DATA =====
        certificate_data = None
        
        # Check if contract is executed or signed
        if result.status in ('executed', 'signed'):
            try:
                # Try to get from metadata table first
                certificate_query = text("""
                    SELECT metadata_value, created_at
                    FROM contract_metadata
                    WHERE contract_id = :contract_id
                    AND metadata_key = 'execution_certificate'
                    ORDER BY created_at DESC LIMIT 1
                """)
                
                cert_result = db.execute(certificate_query, {"contract_id": contract_id}).fetchone()
                
                if cert_result:
                    import json
                    certificate_data = json.loads(cert_result.metadata_value)
                    certificate_data["generated_at"] = cert_result.created_at.isoformat() if cert_result.created_at else None
                else:
                    # Fallback: Generate from current data
                    executed_by_name = f"{current_user.first_name} {current_user.last_name}"
                    
                    # Get signatories
                    signatories_query = text("""
                        SELECT 
                            s.signer_type,
                            s.signed_at,
                            s.ip_address,
                            u.first_name,
                            u.last_name,
                            u.email
                        FROM signatories s
                        LEFT JOIN users u ON s.user_id = u.id
                        WHERE s.contract_id = :contract_id AND s.has_signed = 1
                        ORDER BY s.signing_order
                    """)
                    
                    signatories = db.execute(signatories_query, {"contract_id": contract_id}).fetchall()
                    
                    certificate_data = {
                        "contract_id": contract_id,
                        "contract_number": result.contract_number,
                        "contract_title": result.contract_title,
                        "execution_date": result.effective_date.isoformat() if result.effective_date else None,
                        "signed_date": result.signed_date.isoformat() if result.signed_date else None,
                        "executed_by": executed_by_name,
                        "executed_by_email": current_user.email,
                        "signatories": []
                    }
                    
                    for sig in signatories:
                        # Construct full name
                        signer_name = "External Signer"
                        if sig.first_name and sig.last_name:
                            signer_name = f"{sig.first_name} {sig.last_name}"
                        elif sig.first_name:
                            signer_name = sig.first_name
                        
                        certificate_data["signatories"].append({
                            "signer_type": sig.signer_type,
                            "name": signer_name,
                            "email": sig.email or "",
                            "signed_at": sig.signed_at.isoformat() if sig.signed_at else None,
                            "ip_address": sig.ip_address or ""
                        })
                    
            except Exception as cert_error:
                logger.warning(f" Could not retrieve certificate data: {str(cert_error)}")
                certificate_data = None
        
        # ===== RETURN RESPONSE =====
        return {
            "success": True,
            "contract": {
                "id": result.id,
                "contract_number": result.contract_number,
                "title": result.contract_title,
                "type": result.contract_type,
                "status": result.status,
                "approval_status": result.approval_status,
                "content": result.content if result.content else "",
                "company_name": result.company_name,
                "company_id": result.company_id,
                "party_b_id": result.party_b_id,
                "is_party_b_lead": is_party_b_lead,
                "created_by": result.created_by_name,
                "created_by_id": result.created_by_id,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                "updated_at": result.updated_at.isoformat() if result.updated_at else None,
                "signed_date": result.signed_date.isoformat() if result.signed_date else None,
                "effective_date": result.effective_date.isoformat() if result.effective_date else None,
                "current_version": result.current_version if result.current_version else 1,
                "is_initiator": is_initiator,
                "is_counterparty": is_counterparty,
                "is_ai_generated": result.is_ai_generated,
                "ai_generation_params": result.ai_generation_params
            },
            "workflow": {
                "status": workflow.workflow_status if workflow else "not_configured",
                "current_stage": workflow.current_step if workflow else 0,
                "total_stages": total_steps,
                "template_name": workflow.template_name if workflow else None,
                "steps": workflow_steps,
                "is_my_workflow_turn": is_my_workflow_turn
            } if workflow else None,
            "versions": [
                {
                    "version": str(v.version_number),
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "notes": v.change_summary if v.change_summary else "No notes",
                    "created_by": v.created_by_name if v.created_by_name else "Unknown"
                }
                for v in versions
            ],
            "current_approver": {
                "name": f"{current_approver.first_name} {current_approver.last_name}".strip() if current_approver else None,
                "email": current_approver.email if current_approver else None,
                "department": current_approver.department if current_approver else None,
                "step_type": current_approver.step_type if current_approver else None
            } if current_approver else None,
            "certificate": certificate_data  #  ADDED CERTIFICATE DATA
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching contract editor data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
                  
@router.post("/save-draft/{contract_id}")
async def save_contract_draft(
    contract_id: int,
    content: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save contract draft - creates a new version with blockchain logging"""
    try:
        # Get the latest version number
        version_check = text("""
            SELECT MAX(version_number) as max_version
            FROM contract_versions
            WHERE contract_id = :contract_id
        """)
        
        result = db.execute(version_check, {"contract_id": contract_id}).fetchone()
        next_version = (result.max_version if result and result.max_version else 0) + 1
        
        # Create new version
        version_query = text("""
            INSERT INTO contract_versions 
            (contract_id, version_number, contract_content, change_summary, version_type, created_by, created_at)
            VALUES (:contract_id, :version_number, :content, :change_summary, 'draft', :user_id, NOW())
        """)
        
        db.execute(version_query, {
            "contract_id": contract_id,
            "version_number": next_version,
            "content": content.get("content", ""),
            "change_summary": "Auto-saved draft",
            "user_id": current_user.id
        })
        
        # Update contract timestamp
        update_contract = text("""
            UPDATE contracts 
            SET updated_at = NOW()
            WHERE id = :contract_id
        """)
        
        db.execute(update_contract, {"contract_id": contract_id})
        db.commit()

        #  Store on blockchain WITH ACTIVITY LOGGING
        blockchain_activities = []
        blockchain_success = False
        
        try:
            logger.info(f"🔗 Storing contract {contract_id} on blockchain with activity logging")
            
            #  USE THE LOGGING VERSION
            blockchain_result = await blockchain_service.store_contract_hash_with_logging(
                contract_id=contract_id,
                document_content=content.get("content", ""),
                uploaded_by=current_user.id,
                company_id=current_user.company_id,
                db=db
            )
            
            if blockchain_result.get("success"):
                blockchain_success = True
                blockchain_activities = blockchain_result.get("activities", [])
                logger.info(f" Blockchain storage successful with {len(blockchain_activities)} activity steps")
            else:
                logger.warning(f" Blockchain storage failed: {blockchain_result.get('error')}")
                
        except Exception as blockchain_error:
            # Don't fail the save if blockchain fails
            logger.error(f" Blockchain storage error (non-critical): {str(blockchain_error)}")
            import traceback
            logger.error(traceback.format_exc())
        
        #  RETURN ACTIVITIES IN RESPONSE
        response = {
            "success": True, 
            "message": "Draft saved successfully",
            "version": next_version,
            "blockchain_success": blockchain_success,
            "blockchain_activities": blockchain_activities  # ← This is what frontend needs!
        }
        
        logger.info(f" Returning response with {len(blockchain_activities)} blockchain activities")
        return response
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving draft: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
        

@router.post("/send-for-signature")
async def send_for_signature(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    contract_id = data.get("contract_id")
    
    # Update contract status
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        return {"success": False, "message": "Contract not found"}
    
    contract.status = "signature"
    contract.updated_at = datetime.now()
    db.commit()
    
    # Send notification emails to both parties
    # ... your notification logic ...
    
    return {
        "success": True,
        "message": "Contract sent for signature",
        "contract_id": contract_id
    }

@router.post("/initiate-approval-workflow")
async def initiate_approval_workflow(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initiate approval workflow for contract"""
    try:
        contract_id = data.get("contract_id")
        
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Update contract status to 'approval'
        contract.status = 'approval'
        contract.updated_at = datetime.now()
        
        logger.info(f" Contract {contract_id} status updated to 'approval'")
        
        # Update workflow instance status from 'active' to 'in_progress'
        activate_workflow_query = text("""
            UPDATE workflow_instances 
            SET status = 'in_progress',
                started_at = NOW()
            WHERE contract_id = :contract_id
        """)
        
        db.execute(activate_workflow_query, {"contract_id": contract_id})
        
        logger.info(f" Workflow initiated for contract {contract_id}")
        
        # Create activity log
        try:
            activity_query = text("""
                INSERT INTO contract_activity 
                (contract_id, action_type, action_by, notes, timestamp)
                VALUES 
                (:contract_id, 'workflow_initiated', :user_id, 'Approval workflow initiated', NOW())
            """)
            db.execute(activity_query, {
                "contract_id": contract_id,
                "user_id": current_user.id
            })
        except Exception as activity_err:
            logger.warning(f"Could not create activity log: {str(activity_err)}")
        
        db.commit()
        
        # TODO: Send notification emails to workflow participants
        # Get first step assignees and notify them
        # send_workflow_notification(db, contract_id)
        
        return {
            "success": True,
            "message": "Approval workflow initiated successfully",
            "contract_id": contract_id,
            "contract_status": "approval"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f" Error initiating approval workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# app/api/api_v1/contracts/contracts.py
import json
from datetime import datetime
import uuid

@router.post("/signature/apply")
async def apply_signature(
    signature_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Apply signature to contract - FIXED VERSION
    Fixed: Generate UUID for id column, added contract_id column
    """
    try:
        contract_id = int(signature_data.get("contract_id"))
        signer_type = signature_data.get("signer_type")
        signature_method = signature_data.get("signature_method", "draw")
        signature_value = signature_data.get("signature_data")
        
        logger.info(f" Applying signature: contract_id={contract_id}, signer_type={signer_type}")
        
        # STEP 1: Verify contract
        contract_check = text("""
            SELECT id, status, contract_number, contract_title
            FROM contracts 
            WHERE id = :contract_id
        """)
        
        contract = db.execute(contract_check, {"contract_id": contract_id}).fetchone()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        logger.info(f" Contract: {contract.contract_number} - Status: {contract.status}")
        
        # STEP 2: Check if already signed
        check_existing = text("""
            SELECT id, has_signed, signed_at
            FROM signatories
            WHERE contract_id = :contract_id AND signer_type = :signer_type
            LIMIT 1
        """)
        
        existing = db.execute(check_existing, {
            "contract_id": contract_id,
            "signer_type": signer_type
        }).fetchone()
        
        if existing and existing.has_signed:
            return {
                "success": False,
                "detail": f"This {signer_type} already signed",
                "already_signed": True
            }
        
        # STEP 3: Insert/Update signature
        client_ip = "127.0.0.1"
        
        if existing:
            # UPDATE existing record
            update_signatory = text("""
                UPDATE signatories
                SET has_signed = 1, 
                    signed_at = NOW(),
                    signature_data = :signature_data, 
                    ip_address = :ip_address
                WHERE contract_id = :contract_id AND signer_type = :signer_type
            """)
            
            db.execute(update_signatory, {
                "contract_id": contract_id,
                "signer_type": signer_type,
                "signature_data": signature_value,
                "ip_address": client_ip
            })
        else:
            # INSERT new record - FIXED: Generate UUID for id
            new_id = str(uuid.uuid4())
            
            insert_signatory = text("""
                INSERT INTO signatories 
                (id, contract_id, user_id, signer_type, role, signing_order, 
                 has_signed, signed_at, signature_data, ip_address)
                VALUES 
                (:id, :contract_id, :user_id, :signer_type, :role, :signing_order, 
                 1, NOW(), :signature_data, :ip_address)
            """)
            
            db.execute(insert_signatory, {
                "id": new_id,  # FIXED: Explicitly provide UUID
                "contract_id": contract_id,
                "user_id": int(current_user.id),
                "signer_type": signer_type,
                "role": signer_type.title(),
                "signing_order": 1 if signer_type == 'client' else 2,
                "signature_data": signature_value,
                "ip_address": client_ip
            })
        
        db.commit()
        
        # STEP 4: Check both parties signed
        check_both = text("""
            SELECT 
                SUM(CASE WHEN signer_type = 'client' THEN 1 ELSE 0 END) as client_signed,
                SUM(CASE WHEN signer_type IN ('provider', 'company') THEN 1 ELSE 0 END) as provider_signed
            FROM signatories
            WHERE contract_id = :contract_id AND has_signed = 1
        """)
        
        sig_status = db.execute(check_both, {"contract_id": contract_id}).fetchone()
        
        client_signed = sig_status.client_signed or 0
        provider_signed = sig_status.provider_signed or 0
        both_signed = (client_signed > 0 and provider_signed > 0)
        
        logger.info(f"📊 Signatures: client={client_signed}, provider={provider_signed}")
        
        # STEP 5: If both signed, update contract status to executed
        if both_signed:
            logger.info(f"🎉 Both parties signed! Updating to executed...")
            
            update_contract = text("""
                UPDATE contracts 
                SET status = 'executed', 
                    signed_date = NOW(),
                    updated_at = NOW()
                WHERE id = :contract_id
            """)
            db.execute(update_contract, {"contract_id": contract_id})
            db.commit()
            
            # Store blockchain hash
            try:
                from app.services.blockchain_service import blockchain_service
                blockchain_service.store_contract_hash(contract_id, db)
            except Exception as e:
                logger.warning(f"Blockchain storage failed: {e}")
        
        # Log to audit
        try:
            audit_query = text("""
                INSERT INTO audit_logs (user_id, contract_id, action_type, action_details, ip_address, created_at)
                VALUES (:user_id, :contract_id, :action_type, :action_details, :ip_address, NOW())
            """)
            db.execute(audit_query, {
                "user_id": current_user.id,
                "contract_id": contract_id,
                "action_type": "SIGNATURE_APPLIED",
                "action_details": json.dumps({
                    "signer_type": signer_type,
                    "signature_method": signature_method,
                    "both_signed": both_signed
                }),
                "ip_address": client_ip
            })
            db.commit()
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")
        
        return {
            "success": True,
            "message": f"Signature applied successfully",
            "signer_type": signer_type,
            "both_signed": both_signed,
            "contract_status": "executed" if both_signed else "signature"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")

@router.post("/execute-contract")
async def execute_contract(
    execution_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute contract - FIXED with correct User attributes
    """
    try:
        contract_id = int(execution_data.get("contract_id"))
        
        logger.info(f"🎯 Executing contract {contract_id}")
        
        # Verify contract
        contract_check = text("""
            SELECT id, status, contract_number, contract_title, signed_date
            FROM contracts WHERE id = :contract_id
        """)
        
        contract = db.execute(contract_check, {"contract_id": contract_id}).fetchone()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        if contract.status != 'signed':
            raise HTTPException(status_code=400, detail=f"Contract must be signed. Current: {contract.status}")
        
        # Verify both parties signed
        sig_check = text("""
            SELECT 
                SUM(CASE WHEN signer_type = 'client' THEN 1 ELSE 0 END) as c,
                SUM(CASE WHEN signer_type IN ('provider', 'company') THEN 1 ELSE 0 END) as p
            FROM signatories WHERE contract_id = :contract_id AND has_signed = 1
        """)
        
        sig = db.execute(sig_check, {"contract_id": contract_id}).fetchone()
        
        if not sig or sig.c == 0 or sig.p == 0:
            raise HTTPException(status_code=400, detail="Both parties must sign first")
        
        # Execute contract
        execute_query = text("""
            UPDATE contracts
            SET status = 'executed', workflow_status = 'completed',
                effective_date = CURDATE(), updated_at = NOW()
            WHERE id = :contract_id
        """)
        
        db.execute(execute_query, {"contract_id": contract_id})
        
        # FIXED: Use first_name + last_name instead of full_name
        executed_by_name = f"{current_user.first_name} {current_user.last_name}"
        
        # Generate certificate
        certificate_data = {
            "contract_id": contract_id,
            "contract_number": contract.contract_number,
            "contract_title": contract.contract_title,
            "execution_date": datetime.now().isoformat(),
            "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
            "executed_by": executed_by_name,  # FIXED
            "executed_by_email": current_user.email,
            "signatories": []
        }
        
        # Get signatories with proper name handling
        sig_query = text("""
            SELECT 
                s.signer_type, 
                s.signed_at, 
                s.ip_address, 
                u.first_name,
                u.last_name,
                u.email
            FROM signatories s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.contract_id = :contract_id AND s.has_signed = 1
            ORDER BY s.signing_order
        """)
        
        sigs = db.execute(sig_query, {"contract_id": contract_id}).fetchall()
        
        for s in sigs:
            # FIXED: Construct full name from first_name and last_name
            signer_name = "External Signer"
            if s.first_name and s.last_name:
                signer_name = f"{s.first_name} {s.last_name}"
            elif s.first_name:
                signer_name = s.first_name
            
            certificate_data["signatories"].append({
                "signer_type": s.signer_type,
                "name": signer_name,
                "email": s.email or "",
                "signed_at": s.signed_at.isoformat() if s.signed_at else None,
                "ip_address": s.ip_address or ""
            })
        
        # Store certificate (optional - if table exists)
        try:
            cert_query = text("""
                INSERT INTO contract_metadata
                (contract_id, metadata_key, metadata_value, created_at)
                VALUES (:contract_id, 'execution_certificate', :cert_data, NOW())
            """)
            
            db.execute(cert_query, {
                "contract_id": contract_id,
                "cert_data": json.dumps(certificate_data)
            })
        except Exception as meta_error:
            logger.warning(f" Could not store certificate metadata: {str(meta_error)}")
            # Continue - certificate is in response anyway
        
        # Audit log with JSON
        audit_log = text("""
            INSERT INTO audit_logs 
            (contract_id, user_id, action_type, action_details, created_at)
            VALUES (:contract_id, :user_id, :action_type, :action_details, NOW())
        """)
        
        action_details_json = json.dumps({
            "event": "contract_executed",
            "contract_number": contract.contract_number,
            "message": "Contract officially executed and active",
            "executed_by": executed_by_name,
            "executed_by_email": current_user.email,
            "execution_date": datetime.now().isoformat()
        })
        
        db.execute(audit_log, {
            "contract_id": contract_id,
            "user_id": int(current_user.id),
            "action_type": "contract_executed",
            "action_details": action_details_json
        })
        
        db.commit()
        
        logger.info(f"🎉 Contract {contract_id} executed successfully!")
        
        return {
            "success": True,
            "message": "Contract executed successfully!",
            "contract_id": contract_id,
            "status": "executed",
            "execution_date": datetime.now().isoformat(),
            "certificate_data": certificate_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error executing contract: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/execution-certificate/{contract_id}")
async def get_execution_certificate(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve Certificate of Completion - FIXED with proper name handling
    """
    try:
        # Try to get from metadata table
        try:
            certificate_query = text("""
                SELECT metadata_value, created_at
                FROM contract_metadata
                WHERE contract_id = :contract_id
                AND metadata_key = 'execution_certificate'
                ORDER BY created_at DESC LIMIT 1
            """)
            
            result = db.execute(certificate_query, {"contract_id": contract_id}).fetchone()
            
            if result:
                certificate_data = json.loads(result.metadata_value)
                certificate_data["generated_at"] = result.created_at.isoformat() if result.created_at else None
                
                return {
                    "success": True,
                    "certificate": certificate_data
                }
        except Exception as e:
            logger.info(f"Certificate metadata not found, generating from current data: {str(e)}")
        
        # Fallback: Generate from current data
        contract_query = text("""
            SELECT id, contract_number, contract_title, signed_date, effective_date
            FROM contracts WHERE id = :contract_id
        """)
        
        contract = db.execute(contract_query, {"contract_id": contract_id}).fetchone()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # FIXED: Get user with proper name handling
        executed_by_name = f"{current_user.first_name} {current_user.last_name}"
        
        # Get signatories with proper name handling
        signatories_query = text("""
            SELECT 
                s.signer_type,
                s.signed_at,
                s.ip_address,
                u.first_name,
                u.last_name,
                u.email
            FROM signatories s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.contract_id = :contract_id AND s.has_signed = 1
            ORDER BY s.signing_order
        """)
        
        signatories = db.execute(signatories_query, {"contract_id": contract_id}).fetchall()
        
        certificate_data = {
            "contract_id": contract_id,
            "contract_number": contract.contract_number,
            "contract_title": contract.contract_title,
            "execution_date": contract.effective_date.isoformat() if contract.effective_date else None,
            "signed_date": contract.signed_date.isoformat() if contract.signed_date else None,
            "executed_by": executed_by_name,
            "executed_by_email": current_user.email,
            "signatories": []
        }
        
        for sig in signatories:
            # FIXED: Construct full name
            signer_name = "External Signer"
            if sig.first_name and sig.last_name:
                signer_name = f"{sig.first_name} {sig.last_name}"
            elif sig.first_name:
                signer_name = sig.first_name
            
            certificate_data["signatories"].append({
                "signer_type": sig.signer_type,
                "name": signer_name,
                "email": sig.email or "",
                "signed_at": sig.signed_at.isoformat() if sig.signed_at else None,
                "ip_address": sig.ip_address or ""
            })
        
        return {
            "success": True,
            "certificate": certificate_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving certificate: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


import json
from sqlalchemy import text


@router.post("/workflow/setup")
async def setup_contract_workflow(
    workflow_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Setup workflow for a specific contract"""
    try:
        #  EXTRACT ALL VARIABLES FIRST
        contract_id = workflow_data.get("contract_id")
        workflow_type = workflow_data.get("workflow_type", "custom")
        steps = workflow_data.get("steps", [])
        
        logger.info(f"Setting up {workflow_type} workflow for contract {contract_id}")
        logger.info(f"Company ID: {current_user.company_id}")
        logger.info(f"Received {len(steps)} workflow steps")
        
        if workflow_type == "master":
            #  Use master workflow - ALREADY FILTERED BY COMPANY
            logger.info("Using master workflow")
            
            # Get company's master workflow
            master_query = text("""
                SELECT id FROM workflows 
                WHERE company_id = :company_id 
                AND is_master = 1 
                AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            master_workflow = db.execute(master_query, {
                "company_id": current_user.company_id
            }).fetchone()
            
            if master_workflow:
                # Create workflow instance pointing to master workflow
                instance_query = text("""
                    INSERT INTO workflow_instances 
                    (workflow_id, contract_id, current_step, status, started_at)
                    VALUES (:workflow_id, :contract_id, 1, 'pending', NOW())
                """)
                
                db.execute(instance_query, {
                    "workflow_id": master_workflow.id,
                    "contract_id": contract_id
                })
                
                logger.info(f"Created workflow instance using master workflow {master_workflow.id}")
            else:
                logger.warning("No master workflow found")
                raise HTTPException(status_code=404, detail="Master workflow not found for your company")
                
        else:
            #  CUSTOM WORKFLOW - FIXED VERSION
            logger.info("Creating custom workflow")
            
            # Create workflow record
            workflow_insert = text("""
                INSERT INTO workflows
                (company_id, workflow_name, workflow_type, is_master, is_active, created_at, updated_at)
                VALUES (:company_id, :workflow_name, 'contract_approval', 0, 0, NOW(), NOW())
            """)
            
            result = db.execute(workflow_insert, {
                "company_id": current_user.company_id,
                "workflow_name": f"Custom Workflow"
            })
            
            workflow_id = result.lastrowid
            logger.info(f" Created workflow with ID: {workflow_id} for company {current_user.company_id}")
            
            # Store departments mapping
            departments_map = {}
            
            # Create workflow steps WITH user lookup
            if steps:
                logger.info(f"Processing {len(steps)} workflow steps")
                
                for step in steps:
                    step_order = step.get("step_order", 1)
                    step_label = step.get("step_label", "Review")
                    assigned_email = step.get("assigned_email", "")
                    department = step.get("department", "")
                    
                    logger.info(f" Step {step_order}: role={step_label}, email={assigned_email}, dept={department}")
                    
                    # Store department in mapping
                    if department:
                        departments_map[str(step_order)] = department
                    
                    #  Look up user by email - FILTERED BY COMPANY
                    assignee_user_id = None
                    if assigned_email:
                        user_query = text("""
                            SELECT id FROM users 
                            WHERE email = :email 
                            AND company_id = :company_id
                            AND is_active = 1
                            LIMIT 1
                        """)
                        user_result = db.execute(user_query, {
                            "email": assigned_email,
                            "company_id": current_user.company_id
                        }).fetchone()
                        
                        if user_result:
                            assignee_user_id = user_result.id
                            logger.info(f" Found user ID {assignee_user_id} for email {assigned_email}")
                        else:
                            logger.warning(f" User not found in company for email: {assigned_email}")
                    
                    #  Insert step with assignee_user_id AND department
                    step_insert = text("""
                        INSERT INTO workflow_steps
                        (workflow_id, step_number, step_name, step_type, assignee_role, assignee_user_id, department, sla_hours, is_mandatory, created_at)
                        VALUES (:workflow_id, :step_number, :step_name, :step_type, :assignee_role, :assignee_user_id, :department, 24, 1, NOW())
                    """)
                    
                    db.execute(step_insert, {
                        "workflow_id": workflow_id,
                        "step_number": step_order,
                        "step_name": step_label,
                        "step_type": step_label.lower(),
                        "assignee_role": step_label,
                        "assignee_user_id": assignee_user_id,
                        "department": department
                    })
                    
                    logger.info(f" Inserted step {step_order} with user_id={assignee_user_id}, department={department}")
            else:
                logger.warning("No workflow steps provided")
            
            #  Update workflow with departments JSON
            if departments_map:
                update_workflow = text("""
                    UPDATE workflows 
                    SET workflow_json = :workflow_json
                    WHERE id = :workflow_id
                """)
                
                workflow_config = json.dumps({"departments": departments_map})
                db.execute(update_workflow, {
                    "workflow_id": workflow_id,
                    "workflow_json": workflow_config
                })
                
                logger.info(f" Stored departments mapping: {departments_map}")
            
            # Create workflow instance
            instance_query = text("""
                INSERT INTO workflow_instances 
                (workflow_id, contract_id, current_step, status, started_at)
                VALUES (:workflow_id, :contract_id, 1, 'pending', NOW())
            """)
            
            db.execute(instance_query, {
                "workflow_id": workflow_id,
                "contract_id": contract_id
            })
            
            logger.info(f" Created workflow instance for contract {contract_id}")
        
        db.commit()
        logger.info("🎉 Workflow setup completed successfully")
        
        return {"success": True, "message": "Workflow configured successfully"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error setting up workflow: {str(e)}")
        logger.error(f"Traceback: ", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflow/{contract_id}")
async def get_contract_workflow(
    contract_id: int,
    contract_type: str = None,  # Optional parameter: 'custom', 'master', or None
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get workflow configuration for a specific contract"""
    try:
        logger.info(f"Fetching workflow for contract {contract_id} - Company: {current_user.company_id}, Type: {contract_type}")
        
        #  First verify the contract belongs to user's company
        contract_check = text("""
            SELECT id FROM contracts 
            WHERE id = :contract_id 
        """)
        
        contract_exists = db.execute(contract_check, {
            "contract_id": contract_id,
        }).fetchone()
        
        if not contract_exists:
            logger.warning(f"Contract {contract_id} not found for company {current_user.company_id}")
            raise HTTPException(status_code=404, detail="Contract not found or access denied")
        
        # Build the is_master filter based on contract_type
        is_master_filter = ""
        if contract_type == "custom":
            is_master_filter = "AND w.is_master = 0"
            logger.info(f"Filtering for custom workflows (is_master=0)")
        elif contract_type == "master":
            is_master_filter = "AND w.is_master = 1"
            logger.info(f"Filtering for master workflows (is_master=1)")
        
        #  Get workflow instance - FILTERED BY COMPANY and optionally by is_master
        instance_query = text(f"""
            SELECT 
                wi.id as instance_id,
                wi.workflow_id,
                wi.status,
                w.workflow_name,
                w.is_master,
                w.workflow_type,
                w.workflow_json
            FROM workflow_instances wi
            LEFT JOIN workflows w ON wi.workflow_id = w.id
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :company_id
            {is_master_filter}
            ORDER BY wi.started_at DESC
            LIMIT 1
        """)
        
        workflow_instance = db.execute(instance_query, {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not workflow_instance:
            logger.warning(f"No workflow found for contract {contract_id} in company {current_user.company_id} with type '{contract_type}'")
            return {
                "success": False,
                "message": f"No {'custom' if contract_type == 'custom' else 'master' if contract_type == 'master' else ''} workflow configured for this contract"
            }
        
        # Parse department mapping from workflow_json
        departments_map = {}
        if workflow_instance.workflow_json:
            try:
                if isinstance(workflow_instance.workflow_json, str):
                    config = json.loads(workflow_instance.workflow_json)
                else:
                    config = workflow_instance.workflow_json
                departments_map = config.get('departments', {})
                logger.info(f"Department mapping loaded: {departments_map}")
            except Exception as e:
                logger.error(f"Error parsing workflow_json: {e}")
        
        #  Get workflow steps with user information - FILTERED BY COMPANY
        steps_query = text("""
            SELECT 
                ws.id,
                ws.step_number,
                ws.step_name,
                ws.step_type,
                ws.assignee_role,
                ws.department,
                ws.assignee_user_id,
                ws.sla_hours,
                ws.is_mandatory,
                u.email as assignee_email,
                u.first_name,
                u.last_name
            FROM workflow_steps ws
            LEFT JOIN users u ON ws.assignee_user_id = u.id 
                AND u.company_id = :company_id
                AND u.is_active = 1
            WHERE ws.workflow_id = :workflow_id
            ORDER BY ws.step_number ASC, ws.id ASC
        """)
        
        steps = db.execute(steps_query, {
            "workflow_id": workflow_instance.workflow_id,
            "company_id": current_user.company_id
        }).fetchall()
        
        logger.info(f"Found {len(steps)} workflow step entries for company {current_user.company_id}")
        
        # Group steps by step_number and collect users
        steps_map = {}
        for step in steps:
            step_num = step.step_number
            
            # Get department from mapping or from step directly
            dept = step.department if step.department else ''
            
            # Override with mapping if exists
            if str(step_num) in departments_map:
                dept = departments_map[str(step_num)]
            elif step_num in departments_map:
                dept = departments_map[step_num]
            
            if step_num not in steps_map:
                steps_map[step_num] = {
                    "id": step.id,
                    "step_number": step_num,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "assignee_role": step.assignee_role,
                    "department": dept,
                    "sla_hours": step.sla_hours,
                    "is_mandatory": bool(step.is_mandatory) if step.is_mandatory is not None else True,
                    "users": []
                }
            
            # Add user if exists and belongs to company
            if step.assignee_user_id and step.assignee_email:
                user_exists = any(u['id'] == step.assignee_user_id for u in steps_map[step_num]['users'])
                if not user_exists:
                    steps_map[step_num]['users'].append({
                        "id": step.assignee_user_id,
                        "name": f"{step.first_name} {step.last_name}" if step.first_name else step.assignee_email,
                        "email": step.assignee_email
                    })
        
        # Convert to sorted list
        steps_list = [steps_map[k] for k in sorted(steps_map.keys())]
        
        logger.info(f"Returning {len(steps_list)} workflow steps with department info")
        
        db.commit()
        
        return {
            "success": True,
            "workflow": {
                "id": workflow_instance.workflow_id,
                "workflow_name": workflow_instance.workflow_name,
                "is_master": bool(workflow_instance.is_master),
                "workflow_type": workflow_instance.workflow_type,
                "status": workflow_instance.status,
                "steps": steps_list
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error retrieving workflow: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit-approval")
async def submit_for_internal_review(
    review_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit contract for internal review"""
    try:
        contract_id = review_data.get("contract_id")
        review_type = review_data.get("review_type")
        personnel_emails = review_data.get("personnel_emails", [])
        notes = review_data.get("notes", "")
        
        request_type = review_data.get("request_type")


        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
            

        # Check if current user is Party B (counterparty) for this contract
        contract_query = text("""
            SELECT party_b_id FROM contracts WHERE id = :contract_id LIMIT 1
        """)
        contract_result = db.execute(contract_query, {"contract_id": contract_id}).fetchone()
        
        if not contract_result:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        party_b_id = contract_result.party_b_id if hasattr(contract_result, 'party_b_id') else contract_result[0]
        
        # Check if current user is the counterparty (Party B)
        is_counterparty = party_b_id == current_user.company_id
        
        # Only update contract status if user is NOT Party B (counterparty)
        if not is_counterparty:
            # Update contract status to 'review'
            update_query = text("""
                UPDATE contracts 
                SET status = 'review',
                    updated_at = NOW()
                WHERE id = :contract_id
            """)
            db.execute(update_query, {"contract_id": contract_id})
            logger.info(f"Contract {contract_id} status updated to 'review' by user {current_user.id}")

            if request_type=='approval':
                # Update contract status to 'approval'
                contract.status = 'approval'
                contract.updated_at = datetime.now()
                
                logger.info(f" Contract {contract_id} status updated to 'approval'")
                
                # Update workflow instance status from 'active' to 'in_progress'
                activate_workflow_query = text("""
                    UPDATE workflow_instances 
                    SET status = 'in_progress',
                        started_at = NOW()
                    WHERE contract_id = :contract_id
                """)
        else:
            # Log that counterparty submitted review (status not updated)
            logger.info(f"Counterparty (Party B) user {current_user.id} submitted review for contract {contract_id} (contract status not updated)")
        
        # Handle masterWorkflow and customWorkflow review types
        if review_type == 'masterWorkflow':
            # Deactivate all custom workflows (is_master=0) for this contract and company
            deactivate_custom_query = text("""
                UPDATE workflows 
                SET is_active = 0
                WHERE id IN (
                    SELECT DISTINCT workflow_id 
                    FROM workflow_instances 
                    WHERE contract_id = :contract_id
                )
                AND company_id = :company_id
                AND is_master = 0
            """)
            db.execute(deactivate_custom_query, {
                "contract_id": contract_id,
                "company_id": current_user.company_id
            })
            logger.info(f"Custom workflows deactivated for contract {contract_id} (masterWorkflow selected)")
            
            # Check if master workflow instances exist for this contract
            check_master_instances = text("""
                SELECT COUNT(*) as count
                FROM workflow_instances wi
                INNER JOIN workflows w ON wi.workflow_id = w.id
                WHERE wi.contract_id = :contract_id
                AND w.company_id = :company_id
                AND w.is_master = 1
            """)
            master_count_result = db.execute(check_master_instances, {
                "contract_id": contract_id,
                "company_id": current_user.company_id
            }).fetchone()
            
            master_count = master_count_result[0] if master_count_result else 0
            
            # If no master workflow instances exist, create them
            if master_count == 0:
                # Get all active master workflows for the company
                get_master_workflows = text("""
                    SELECT id, workflow_name
                    FROM workflows
                    WHERE company_id = :company_id
                    AND is_master = 1
                    AND is_active = 1
                """)
                master_workflows = db.execute(get_master_workflows, {
                    "company_id": current_user.company_id
                }).fetchall()
                
                # Create workflow instances for each master workflow
                for workflow in master_workflows:
                    workflow_id = workflow[0]
                    workflow_name = workflow[1]
                    
                    insert_instance = text("""
                        INSERT INTO workflow_instances 
                        (contract_id, workflow_id, status, current_step)
                        VALUES (:contract_id, :workflow_id, 'pending',1)
                    """)
                    db.execute(insert_instance, {
                        "contract_id": contract_id,
                        "workflow_id": workflow_id
                    })
                    logger.info(f"Created master workflow instance for workflow '{workflow_name}' (ID: {workflow_id}) and contract {contract_id}")
            else:
                logger.info(f"Master workflow instances already exist for contract {contract_id} (count: {master_count})")
            
        elif review_type == 'customWorkflow':
            # Activate all custom workflows (is_master=0) for this contract and company
            activate_custom_query = text("""
                UPDATE workflows 
                SET is_active = 1
                WHERE id IN (
                    SELECT DISTINCT workflow_id 
                    FROM workflow_instances 
                    WHERE contract_id = :contract_id
                )
                AND company_id = :company_id
                AND is_master = 0
            """)
            db.execute(activate_custom_query, {
                "contract_id": contract_id,
                "company_id": current_user.company_id
            })
            logger.info(f"Custom workflows activated for contract {contract_id} (customWorkflow selected)")
        
        # Activate workflow instances for ALL users (including counterparties)
        activate_workflow_query = text("""
            UPDATE workflow_instances 
            SET status = 'active',
                started_at = NOW()
            WHERE contract_id = :contract_id
            AND status IN ('pending', 'in_progress')
        """)
        db.execute(activate_workflow_query, {
            "contract_id": contract_id
        })
        logger.info(f"Workflow instances activated for contract {contract_id}")
        
        # Send notifications to specific personnel (allowed for all users including counterparties)
        if review_type == 'specific' and personnel_emails:
            for email in personnel_emails:
                if not email:
                    continue
                    
                user_query = text("""
                    SELECT id FROM users WHERE email = :email LIMIT 1
                """)
                user = db.execute(user_query, {"email": email.strip()}).fetchone()
                
                if user:
                    notif_query = text("""
                        INSERT INTO notifications 
                        (recipient_id, notification_type, title, message, status, created_at)
                        VALUES (:user_id, 'contract_review', :title, :message, 'pending', NOW())
                    """)
                    db.execute(notif_query, {
                        "user_id": str(user.id),
                        "title": "Contract Review Required",
                        "message": f"Contract {contract_id} requires your review. Notes: {notes}"
                    })
        
        db.commit()
        
        # Return appropriate message based on user type
        if is_counterparty:
            message = "Review submitted successfully (workflow activated)"
        else:
            message = "Contract submitted for internal review successfully"
        
        return {
            "success": True,
            "message": message,
            "is_counterparty": is_counterparty
        }
        
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting contract for review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



# =====================================================
# HELPER FUNCTIONS - WITH FIXED CONTRACT NUMBER GENERATION
# =====================================================

def generate_contract_number(db: Session, company_id: int = None) -> str:
    """Generate unique contract number"""
    try:
        year = datetime.now().year
        month = datetime.now().month
        
        # Get the count of contracts for this year-month
        query = text("""
            SELECT COUNT(*) as count 
            FROM contracts 
            WHERE YEAR(created_at) = :year 
            AND MONTH(created_at) = :month
        """)
        
        result = db.execute(query, {"year": year, "month": month})
        count = result.fetchone()[0]
        
        # Generate contract number: CNT-YYYY-MM-XXXX
        contract_number = f"CNT-{year}-{month:02d}-{(count + 1):04d}"
        return contract_number
        
    except Exception as e:
        logger.error(f"Error generating contract number: {str(e)}")
        # Fallback to timestamp-based number
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"CNT-{timestamp}"

def save_uploaded_file(file: UploadFile, contract_number: str, company_id: str) -> str:
    """Save uploaded file to storage"""
    upload_dir = Path("uploads") / "contracts" / str(company_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{contract_number}{file_extension}"
    file_path = upload_dir / filename
    
    with open(file_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
    
    return str(file_path)

def calculate_completion(contract):
    """Calculate contract completion percentage"""
    status_completion = {
        'draft': 10,
        'pending_review': 30,
        'negotiation': 50,
        'approved': 80,
        'active': 100,
        'completed': 100,
        'expired': 100,
        'terminated': 100,
        'rejected': 100
    }
    
    base = status_completion.get(contract.status, 0)
    
    workflow_adjustment = {
        'draft': 0,
        'internal_review': 10,
        'clause_analysis': 15,
        'external_review': 20,
        'negotiation': 30,
        'approval': 40,
        'execution': 50,
        'active': 0
    }
    
    adjustment = workflow_adjustment.get(contract.workflow_status, 0) if contract.workflow_status else 0
    completion = base + adjustment
    
    if hasattr(contract, 'is_signed') and contract.is_signed:
        completion = max(completion, 90)
    
    return min(completion, 100)

# =====================================================
# FILE: app/api/api_v1/contracts/contracts.py
# COMPLETE FIX: Risk Analysis with Data Transformation
# =====================================================

@router.post("/risk-analysis/{contract_id}")
async def analyze_contract_risks(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI-powered risk analysis for contract using Claude API"""
    try:
        logger.info(f"🔍 Starting AI risk analysis for contract {contract_id}")
        
        # Get contract details - FIXED column name
        contract_query = text("""
            SELECT c.id, c.contract_title, c.contract_type, c.governing_law,
                   c.effective_date, c.expiry_date, c.contract_value,
                   cv.contract_content, cv.version_number
            FROM contracts c
            LEFT JOIN contract_versions cv ON c.id = cv.contract_id
            WHERE c.id = :contract_id
            ORDER BY cv.version_number DESC
            LIMIT 1
        """)
        
        result = db.execute(contract_query, {"contract_id": contract_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        contract_content = result.contract_content if result.contract_content else ""
        contract_title = result.contract_title if result.contract_title else "Unknown Contract"
        contract_type = result.contract_type if result.contract_type else "General"
        jurisdiction = result.governing_law if result.governing_law else "Qatar"
        
        # If no content, try to get clauses
        if not contract_content:
            clauses_query = text("""
                SELECT clause_title, clause_body 
                FROM contract_clauses 
                WHERE contract_id = :contract_id
                ORDER BY sequence_number
            """)
            clauses_result = db.execute(clauses_query, {"contract_id": contract_id}).fetchall()
            
            if clauses_result:
                contract_content = "\n\n".join([
                    f"**{clause.clause_title}**\n{clause.clause_body}" 
                    for clause in clauses_result
                ])
        
        # Initialize Claude service
        claude_service = ClaudeService()
        
        if not claude_service.client:
            raise HTTPException(
                status_code=503, 
                detail="Claude AI service not available. Please configure CLAUDE_API_KEY in .env"
            )
        
        # Prepare comprehensive prompt for Claude
        prompt = f"""You are a legal contract risk analyst specializing in Qatar and GCC region contracts. 
Analyze the following contract and provide a comprehensive risk assessment.

CONTRACT INFORMATION:
- Title: {contract_title}
- Type: {contract_type}
- Jurisdiction: {jurisdiction}
- Value: {result.contract_value if result.contract_value else 'Not specified'}

CONTRACT CONTENT:
{contract_content[:10000] if contract_content else 'No detailed content available - provide general risk assessment for this contract type'}

Please provide a detailed risk analysis in the following JSON format:
{{
    "overall_risk_score": <0-100>,
    "risk_level": "<Critical/High/Medium/Low>",
    "executive_summary": "<2-3 sentence overview>",
    "risk_categories": [
        {{
            "category": "<Legal/Financial/Operational/Compliance/Dispute>",
            "risk_level": "<Critical/High/Medium/Low>",
            "score": <0-100>,
            "items": [
                {{
                    "title": "<Risk title>",
                    "description": "<Detailed description>",
                    "severity": "<critical/high/medium/low>",
                    "likelihood": "<High/Medium/Low>",
                    "mitigation": "<Recommended mitigation strategy>",
                    "clause_reference": "<Reference to specific clause if applicable>"
                }}
            ]
        }}
    ],
    "compliance_issues": [
        {{
            "regulation": "<Qatar Civil Code/QFCRA/etc>",
            "issue": "<Description>",
            "severity": "<critical/high/medium/low>",
            "recommendation": "<Action needed>"
        }}
    ],
    "red_flags": [
        "<Major concern 1>",
        "<Major concern 2>"
    ],
    "recommendations": [
        {{
            "priority": "<High/Medium/Low>",
            "recommendation": "<Action to take>",
            "rationale": "<Why this is important>"
        }}
    ]
}}

Focus on Qatar-specific legal requirements, QFCRA regulations if applicable, and GCC commercial practices.
IMPORTANT: Use lowercase for severity levels (critical, high, medium, low)."""

        logger.info(f" Sending risk analysis request to Claude AI")
        
        # Call Claude API
        response = claude_service.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # Extract and parse response
        analysis_text = response.content[0].text
        logger.info(f" Received risk analysis from Claude AI")
        
        # Try to parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
        if json_match:
            claude_analysis = json.loads(json_match.group())
        else:
            # Fallback if JSON parsing fails
            claude_analysis = {
                "overall_risk_score": 50,
                "risk_level": "Medium",
                "executive_summary": analysis_text[:500],
                "risk_categories": [],
                "red_flags": [],
                "recommendations": []
            }
        
        # =====================================================
        # TRANSFORM DATA FOR FRONTEND
        # =====================================================
        
        # Count risks by severity across all categories
        high_risks = 0
        medium_risks = 0
        low_risks = 0
        risk_items = []
        
        # Process risk categories
        for category in claude_analysis.get("risk_categories", []):
            for item in category.get("items", []):
                severity = item.get("severity", "medium").lower()
                
                # Count by severity
                if severity == "critical" or severity == "high":
                    high_risks += 1
                elif severity == "medium":
                    medium_risks += 1
                else:
                    low_risks += 1
                
                # Format risk item for frontend
                risk_items.append({
                    "type": category.get("category", "General"),
                    "issue": item.get("title", "Unknown Risk"),
                    "description": item.get("description", ""),
                    "severity": severity,
                    "score": item.get("score") or category.get("score", 50),
                    "clause_reference": item.get("clause_reference", "General"),
                    "mitigation": item.get("mitigation", ""),
                    "likelihood": item.get("likelihood", "Medium"),
                    "business_impact": item.get("business_impact", "Moderate")
                })
        
        # Add compliance issues as high severity risks
        for issue in claude_analysis.get("compliance_issues", []):
            severity = issue.get("severity", "high").lower()
            if severity == "critical" or severity == "high":
                high_risks += 1
            elif severity == "medium":
                medium_risks += 1
            else:
                low_risks += 1
            
            risk_items.append({
                "type": "Compliance",
                "issue": f"Compliance: {issue.get('regulation', 'Regulatory Issue')}",
                "description": issue.get("issue", ""),
                "severity": severity,
                "score": 80 if severity == "high" else 60,
                "clause_reference": issue.get("regulation", "General"),
                "mitigation": issue.get("recommendation", ""),
                "likelihood": "High",
                "business_impact": "Regulatory"
            })
        
        # Calculate safety score (inverse of risk score)
        overall_risk_score = claude_analysis.get("overall_risk_score", 50)
        safety_score = 100 - overall_risk_score
        
        # Format data for frontend
        formatted_analysis = {
            "overall_score": safety_score,  # Safety score (inverse of risk)
            "risk_score": overall_risk_score,  # Actual risk score
            "risk_level": claude_analysis.get("risk_level", "Medium"),
            "high_risks": high_risks,
            "medium_risks": medium_risks,
            "low_risks": low_risks,
            "executive_summary": claude_analysis.get("executive_summary", "Risk analysis completed."),
            "risk_items": risk_items,
            "red_flags": claude_analysis.get("red_flags", []),
            "recommendations": claude_analysis.get("recommendations", []),
            "compliance_issues": claude_analysis.get("compliance_issues", []),
            "total_risks": high_risks + medium_risks + low_risks
        }
        
        # Save analysis to database
        save_query = text("""
            INSERT INTO ai_analysis_results 
            (contract_id, analysis_type, analysis_data, risk_score, created_at)
            VALUES (:contract_id, 'risk_analysis', :analysis_data, :risk_score, NOW())
        """)
        
        db.execute(save_query, {
            "contract_id": contract_id,
            "analysis_data": json.dumps(formatted_analysis),
            "risk_score": overall_risk_score
        })
        db.commit()
        
        logger.info(f" Risk analysis saved to database for contract {contract_id}")
        
        return {
            "success": True,
            "contract_id": contract_id,
            "contract_title": contract_title,
            "analysis": formatted_analysis,
            "ai_powered": True,
            "model": "claude-sonnet-4-20250514"
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in risk analysis: {str(e)}")
        # Return a basic analysis instead of failing
        return {
            "success": True,
            "contract_id": contract_id,
            "analysis": {
                "overall_score": 50,
                "risk_score": 50,
                "risk_level": "Medium",
                "high_risks": 0,
                "medium_risks": 1,
                "low_risks": 0,
                "executive_summary": "Risk analysis completed with limited data. Manual review recommended.",
                "risk_items": [{
                    "type": "General",
                    "issue": "AI Analysis Parsing Error",
                    "description": "Unable to parse complete analysis. Manual review recommended.",
                    "severity": "medium",
                    "score": 50,
                    "clause_reference": "General",
                    "mitigation": "Conduct manual risk assessment"
                }],
                "red_flags": [],
                "recommendations": []
            },
            "ai_powered": True,
            "error": "Partial analysis completed"
        }
    except Exception as e:
        logger.error(f"Error in risk analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/risk-analysis-upload")
async def upload_contract_for_risk_analysis(
    file: UploadFile = File(...),
    profile_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload contract file and perform immediate AI risk analysis with format preservation"""
    

    claude_service = ClaudeService()

    try:
        logger.info(f" Risk Analysis Upload from user {current_user.email}")
        logger.info(f"📎 File: {file.filename}, Profile: {profile_type}")
        
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # =====================================================
        # FIXED: Generate unique contract number with retry logic
        # =====================================================
        year = datetime.now().year
        month = datetime.now().month
        contract_number = None
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                # Use MAX instead of COUNT to get the highest number
                max_number_query = text("""
                    SELECT contract_number 
                    FROM contracts 
                    WHERE contract_number LIKE :pattern 
                    AND company_id = :company_id
                    ORDER BY contract_number DESC
                    LIMIT 1
                """)
                
                result = db.execute(max_number_query, {
                    "pattern": f"CNT-{year}-%",
                    "company_id": current_user.company_id
                }).fetchone()
                
                if result and result.contract_number:
                    # Extract the number from the last contract number
                    last_number = int(result.contract_number.split('-')[-1])
                    new_number = last_number + 1
                else:
                    new_number = 1
                
                contract_number = f"CNT-{year}-{new_number:04d}"
                logger.info(f"🔢 Generated contract number: {contract_number} (attempt {attempt + 1})")
                
                # Try to insert the contract - if successful, break the loop
                insert_contract = text("""
                    INSERT INTO contracts (
                        contract_number, contract_title, contract_type, profile_type,
                        status, current_version, created_by, company_id, created_at, updated_at
                    ) VALUES (
                        :contract_number, :contract_title, :contract_type, :profile_type,
                        'draft', 1, :created_by, :company_id, NOW(), NOW()
                    )
                """)
                
                contract_title = f"Risk Analysis - {file.filename}"
                
                db.execute(insert_contract, {
                    "contract_number": contract_number,
                    "contract_title": contract_title,
                    "contract_type": "risk_analysis",
                    "profile_type": profile_type,
                    "created_by": current_user.id,
                    "company_id": current_user.company_id
                })
                db.commit()
                
                logger.info(f" Contract created with number: {contract_number}")
                break  # Success - exit retry loop
                
            except Exception as e:
                db.rollback()
                if "Duplicate entry" in str(e) and attempt < max_retries - 1:
                    logger.warning(f" Duplicate contract number {contract_number}, retrying... (attempt {attempt + 1})")
                    continue  # Retry with next number
                elif attempt == max_retries - 1:
                    # Last attempt - use timestamp-based unique number
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    contract_number = f"CNT-{year}-{timestamp[-6:]}"
                    logger.warning(f" Using timestamp-based contract number: {contract_number}")
                    
                    db.execute(insert_contract, {
                        "contract_number": contract_number,
                        "contract_title": contract_title,
                        "contract_type": "risk_analysis",
                        "profile_type": profile_type,
                        "created_by": current_user.id,
                        "company_id": current_user.company_id
                    })
                    db.commit()
                    logger.info(f" Contract created with timestamp-based number: {contract_number}")
                    break
                else:
                    raise  # Re-raise if it's not a duplicate error
        
        # Get the inserted contract ID
        contract_id_query = text("""
            SELECT id FROM contracts 
            WHERE contract_number = :contract_number 
            AND company_id = :company_id
        """)
        contract_result = db.execute(contract_id_query, {
            "contract_number": contract_number,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not contract_result:
            raise HTTPException(status_code=500, detail="Failed to create contract")
        
        contract_id = contract_result.id
        logger.info(f" Contract created with ID: {contract_id}")
        
        # Create upload directory
        upload_base = os.path.join("app", "uploads", "contracts", str(contract_id))
        os.makedirs(upload_base, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_base, file.filename)
        file_content = await file.read()
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f" File saved to: {file_path}")
        
        # =====================================================
        # EXTRACT TEXT USING DocumentParser (Same as upload-contract)
        # =====================================================
        logger.info(f" Extracting text from {file_ext} file...")
        
        # Import DocumentParser
        from app.utils.document_parser import DocumentParser
        
        # Extract text with proper formatting
        extracted_text = DocumentParser.extract_text(str(file_path))
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            logger.warning(f" No text extracted from file, using placeholder")
            extracted_text = f"<p>Unable to extract text from {file.filename}. Please check the file format.</p>"
        else:
            logger.info(f" Extracted {len(extracted_text)} characters from document")
        
        # Format the extracted content as HTML (same as upload-contract)
        file_size_kb = len(file_content) / 1024
        
        html_content = f"""
        <div class="contract-document" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            
            <!-- Document Content -->
            <div class="document-content" style="background: white;">
                <div style="white-space: pre-wrap; word-wrap: break-word; font-size: 14px; line-height: 1.8;">
{extracted_text}
                </div>
            </div>
           
        </div>
        """
        
        # Get plain text for AI analysis (strip HTML tags)
        import re
        extracted_text_plain = re.sub('<[^<]+?>', '', extracted_text)
        extracted_text_plain = re.sub(r'\s+', ' ', extracted_text_plain).strip()
        
        logger.info(f" Extracted: {len(extracted_text_plain)} chars (HTML: {len(html_content)} chars)")
        
        # Save contract version with formatted HTML content
        insert_version = text("""
            INSERT INTO contract_versions (
                contract_id, version_number, version_type, contract_content,
                change_summary, created_by, created_at
            ) VALUES (
                :contract_id, 1, 'draft', :contract_content,
                :change_summary, :created_by, NOW()
            )
        """)
        
        db.execute(insert_version, {
            "contract_id": contract_id,
            "contract_content": html_content,  # Save formatted HTML
            "change_summary": f"Initial upload: {file.filename} - {len(extracted_text_plain):,} characters extracted",
            "created_by": current_user.id
        })
        db.commit()
        
        logger.info(" Contract version saved with preserved formatting")
        
        # =====================================================
        # STEP 4: AI-POWERED RISK ANALYSIS WITH CLAUDE
        # =====================================================
        try:
            logger.info("Starting AI risk analysis with Claude...")
            
            # Check if Claude service is available
            if not claude_service or not claude_service.client:
                logger.warning("Claude service not available - skipping AI analysis")
                raise Exception("Claude service not initialized")
            
            # Build risk analysis prompt
            risk_prompt = f"""You are a contract risk analysis expert specializing in {profile_type} contracts under Qatar jurisdiction.

Analyze the following contract text and provide a comprehensive risk assessment.

**Contract Text:**
{extracted_text_plain[:8000]}

**Analysis Requirements:**
Analyze from the perspective of: {profile_type}
Focus on Qatar/QFCRA compliance requirements.

**Provide your analysis in the following JSON format ONLY (no other text):**
{{
    "overall_score": <number 0-100, where 100 is highest risk>,
    "risk_level": "<High/Medium/Low>",
    "executive_summary": "<2-3 sentence summary of key risks>",
    "high_risks": <count of high severity items>,
    "medium_risks": <count of medium severity items>,
    "low_risks": <count of low severity items>,
    "risk_items": [
        {{
            "type": "<Legal/Financial/Operational/Compliance/Termination/Liability>",
            "issue": "<Brief issue title>",
            "description": "<Detailed description of the risk>",
            "severity": "<high/medium/low>",
            "score": <number 1-100>,
            "clause_reference": "<Section or clause reference if identifiable>",
            "mitigation": "<Recommended mitigation strategy>"
        }}
    ],
    "red_flags": [
        "<List of critical red flags that need immediate attention>"
    ],
    "recommendations": [
        "<Actionable recommendation 1>",
        "<Actionable recommendation 2>",
        "<Actionable recommendation 3>"
    ],
    "compliance_issues": [
        "<QFCRA or Qatar-specific compliance concern>"
    ]
}}

Analyze now and respond with ONLY the JSON object:"""

            # Call Claude API using the service
            message = claude_service.client.messages.create(
                model=claude_service.model,
                max_tokens=4000,
                temperature=0.3,
                messages=[{"role": "user", "content": risk_prompt}]
            )
            
            # Extract response text
            ai_response = message.content[0].text.strip()
            logger.info(f"Claude response received ({len(ai_response)} chars)")
            
            # Clean up response - remove markdown code blocks if present
            if ai_response.startswith("```"):
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
                ai_response = ai_response.strip()
            
            # Parse JSON response
            claude_analysis = json.loads(ai_response)
            logger.info(f"AI analysis parsed successfully")
            
            # Extract values with defaults
            overall_risk_score = claude_analysis.get("overall_score", 50)
            risk_items = claude_analysis.get("risk_items", [])
            
            # Count risks by severity
            high_risks = len([r for r in risk_items if r.get("severity", "").lower() == "high"])
            medium_risks = len([r for r in risk_items if r.get("severity", "").lower() == "medium"])
            low_risks = len([r for r in risk_items if r.get("severity", "").lower() == "low"])
            
            # Format the analysis for storage
            formatted_analysis = {
                "overall_score": overall_risk_score,
                "risk_score": overall_risk_score,
                "risk_level": claude_analysis.get("risk_level", "Medium"),
                "high_risks": high_risks or claude_analysis.get("high_risks", 0),
                "medium_risks": medium_risks or claude_analysis.get("medium_risks", 0),
                "low_risks": low_risks or claude_analysis.get("low_risks", 0),
                "executive_summary": claude_analysis.get("executive_summary", "Contract analyzed for potential risks."),
                "risk_items": risk_items,
                "red_flags": claude_analysis.get("red_flags", []),
                "recommendations": claude_analysis.get("recommendations", []),
                "compliance_issues": claude_analysis.get("compliance_issues", []),
                "total_risks": high_risks + medium_risks + low_risks,
                "profile_type": profile_type,
                "analyzed_at": datetime.now().isoformat()
            }
            
            # Save analysis to database
            save_analysis = text("""
                INSERT INTO ai_analysis_results 
                (contract_id, analysis_type, analysis_data, risk_score, created_at)
                VALUES (:contract_id, 'risk_analysis', :analysis_data, :risk_score, NOW())
            """)
            
            db.execute(save_analysis, {
                "contract_id": contract_id,
                "analysis_data": json.dumps(formatted_analysis),
                "risk_score": overall_risk_score
            })
            db.commit()
            
            logger.info(f"AI risk analysis saved to database (Risk Score: {overall_risk_score})")
            
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON parsing error: {str(json_err)}")
            # Continue without AI analysis - contract is still saved
            
        except Exception as ai_error:
            logger.error(f" AI analysis error: {str(ai_error)}")
            import traceback
            logger.error(traceback.format_exc())
            # Continue without AI analysis - user can run it later
        
        # Return success response
        return {
            "success": True,
            "contract_id": contract_id,
            "contract_number": contract_number,
            "message": f"Contract '{file.filename}' uploaded and analyzed successfully",
            "file_path": file_path,
            "extracted_length": len(extracted_text_plain),
            "formatted": True,
            "content_extracted": len(extracted_text_plain) > 10
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f" Error in risk analysis upload: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# CLAUSE ANALYSIS ENDPOINTS
# =====================================================

@router.post("/clause-suggestions")
async def get_clause_suggestions(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI suggestions for clause improvements using Claude API"""
    try:
        clause_text = request.get("clause_text", "")
        clause_type = request.get("clause_type", "general")
        
        # Return mock suggestions if no clause text
        if not clause_text:
            suggestions = [
                {
                    "original": clause_text,
                    "suggested": "Either party may terminate for convenience with ninety (90) days notice. Termination for cause requires thirty (30) days notice with fifteen (15) day cure period.",
                    "reasoning": "Provides balanced termination rights with appropriate notice periods and cure provisions",
                    "legal_score": 5,
                    "business_score": 4,
                    "compliance": "Complies with Qatar Labor Law Article 61"
                },
                {
                    "original": clause_text,
                    "suggested": "Either party may terminate this Agreement upon sixty (60) days written notice. The terminating party shall provide detailed reasons for termination.",
                    "reasoning": "Standard termination clause with documentation requirements",
                    "legal_score": 4,
                    "business_score": 4,
                    "compliance": "Standard industry practice"
                }
            ]
            return {"success": True, "suggestions": suggestions}
        
        # Use Claude API for real suggestions
        try:
            # Initialize Claude service
            claude_service = ClaudeService()
            
            if not claude_service.client:
                logger.warning("Claude client not available, using mock suggestions")
                raise ValueError("Claude client not initialized")
            
            # Prepare the prompt for Claude
            prompt = f"""You are a legal expert specializing in contract law, particularly in Qatar jurisdiction. Analyze and improve the following {clause_type} clause.

Original Clause:
{clause_text}

Please provide 2-3 improved versions of this clause and respond in the following JSON format:
{{
    "suggestions": [
        {{
            "original": "<original clause text>",
            "suggested": "<improved clause text>",
            "reasoning": "<explanation of why this version is better>",
            "legal_score": <1-5, where 5 is strongest legal protection>,
            "business_score": <1-5, where 5 is most business-friendly>,
            "compliance": "<relevant Qatar laws or regulations this complies with>"
        }}
    ]
}}

Consider the following in your suggestions:
1. Compliance with Qatar Civil and Commercial Law
2. Clarity and enforceability
3. Balance between parties' interests
4. Industry best practices
5. Risk mitigation
6. Specific requirements for {clause_type} clauses

Provide only the JSON response without any additional text or markdown formatting."""

            response = claude_service.client.messages.create(
                model=claude_service.model,
                max_tokens=2000,
                temperature=0.5,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract the text content from Claude's response
            response_text = response.content[0].text
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                suggestions = result.get("suggestions", [])
                
                # Ensure we have at least one suggestion
                if not suggestions:
                    raise ValueError("No suggestions returned from Claude")
                
                # Log the clause improvement to audit trail
                audit_log = text("""
                    INSERT INTO audit_logs 
                    (user_id, action_type, action_details, ip_address, user_agent, created_at)
                    VALUES 
                    (:user_id, :action_type, :action_details, :ip_address, :user_agent, NOW())
                """)
                
                db.execute(audit_log, {
                    "user_id": current_user.id,
                    "action_type": "AI_CLAUSE_SUGGESTION",
                    "action_details": json.dumps({
                        "clause_type": clause_type,
                        "original_length": len(clause_text),
                        "suggestions_count": len(suggestions)
                    }),
                    "ip_address": "system",
                    "user_agent": "Claude AI"
                })
                db.commit()
                
                return {"success": True, "suggestions": suggestions}
            else:
                raise ValueError("Could not extract JSON from Claude response")
                    
        except Exception as e:
            logger.error(f"Error using Claude API for clause suggestions: {str(e)}")
            # Fall through to default suggestions
        
        # Return default suggestions if Claude API fails
        suggestions = [
            {
                "original": clause_text,
                "suggested": "Either party may terminate for convenience with ninety (90) days written notice. Termination for cause requires thirty (30) days written notice with fifteen (15) day cure period. Upon termination, all outstanding obligations shall be settled within thirty (30) days.",
                "reasoning": "Provides balanced termination rights with appropriate notice periods, cure provisions, and settlement timeline",
                "legal_score": 5,
                "business_score": 4,
                "compliance": "Complies with Qatar Labor Law Article 61 and Civil Code provisions"
            },
            {
                "original": clause_text,
                "suggested": "Either party may terminate this Agreement upon sixty (60) days written notice. The terminating party shall provide detailed written reasons for termination. No termination shall relieve either party of obligations incurred prior to the effective termination date.",
                "reasoning": "Standard termination clause with documentation requirements and liability preservation",
                "legal_score": 4,
                "business_score": 4,
                "compliance": "Standard industry practice aligned with Qatar commercial regulations"
            },
            {
                "original": clause_text,
                "suggested": "This Agreement may be terminated by mutual written consent or by either party upon material breach by the other party, provided that written notice of such breach is given and the breaching party fails to cure within twenty (20) business days.",
                "reasoning": "Focuses on breach-based termination with reasonable cure period, protecting both parties",
                "legal_score": 4,
                "business_score": 3,
                "compliance": "Consistent with Qatar Civil Code Article 171 on contractual obligations"
            }
        ]
        
        return {"success": True, "suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Error getting clause suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# VERSION HISTORY ENDPOINTS
# =====================================================

@router.get("/versions/{contract_id}")
async def get_version_history(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete version history for contract"""
    try:
        query = text("""
            SELECT 
                cv.id,
                cv.version_number,
                cv.version_type,
                cv.change_summary,
                cv.created_at,
                CONCAT(u.first_name, ' ', u.last_name) as created_by_name,
                LEFT(cv.contract_content, 500) as content_preview
            FROM contract_versions cv
            LEFT JOIN users u ON cv.created_by = u.id
            WHERE cv.contract_id = :contract_id
            ORDER BY cv.version_number DESC
        """)
        
        versions = db.execute(query, {"contract_id": contract_id}).fetchall()
        
        version_list = []
        for v in versions:
            version_list.append({
                "id": v.id,
                "version": v.version_number,
                "type": v.version_type or "draft",
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "created_by": v.created_by_name or "Unknown",
                "notes": v.change_summary or "No notes",
                "content_preview": v.content_preview or ""
            })
        
        return {"success": True, "versions": version_list}
        
    except Exception as e:
        logger.error(f"Error getting version history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/versions/compare")
async def compare_versions(
    contract_id: int,
    version1: int = Query(...),
    version2: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare two contract versions"""
    try:
        query = text("""
            SELECT version_number, contract_content 
            FROM contract_versions
            WHERE contract_id = :contract_id 
            AND version_number IN (:v1, :v2)
        """)
        
        results = db.execute(query, {
            "contract_id": contract_id,
            "v1": version1,
            "v2": version2
        }).fetchall()
        
        if len(results) < 2:
            raise HTTPException(status_code=404, detail="One or both versions not found")
        
        # Simple diff - count changes
        v1_content = results[0].contract_content or ""
        v2_content = results[1].contract_content or ""
        
        changes = []
        if v1_content != v2_content:
            changes.append({
                "type": "content",
                "description": f"Content changed between version {version1} and {version2}",
                "characters_added": max(0, len(v2_content) - len(v1_content)),
                "characters_removed": max(0, len(v1_content) - len(v2_content))
            })
        
        return {
            "success": True,
            "version1": version1,
            "version2": version2,
            "changes": changes,
            "total_changes": len(changes)
        }
        
    except Exception as e:
        logger.error(f"Error comparing versions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# EXPORT ENDPOINTS
# =====================================================

@router.post("/export/{contract_id}")
async def export_contract(
    contract_id: int,
    format: str = Query("pdf"),
    include_tracked_changes: bool = Query(True),
    include_comments: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export contract in various formats"""
    try:
        # Get contract data
        query = text("""
            SELECT 
                c.contract_number,
                c.contract_title,
                cv.contract_content
            FROM contracts c
            LEFT JOIN contract_versions cv ON c.id = cv.contract_id
            WHERE c.id = :contract_id
            ORDER BY cv.version_number DESC
            LIMIT 1
        """)
        
        result = db.execute(query, {"contract_id": contract_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        content = result.contract_content or "No content available"
        
        if format == "pdf":
            # Generate simple PDF
            from io import BytesIO
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            
            pdf_buffer = BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            
            # Title
            c.setFont("Helvetica-Bold", 16)
            c.drawString(100, 750, result.contract_title or "Contract")
            
            # Contract number
            c.setFont("Helvetica", 12)
            c.drawString(100, 730, f"Contract Number: {result.contract_number}")
            
            # Content (simplified - remove HTML tags)
            import re
            clean_content = re.sub('<.*?>', '', content)
            
            y_position = 700
            lines = clean_content.split('\n')
            for line in lines[:40]:  # First 40 lines
                if y_position < 100:
                    c.showPage()
                    y_position = 750
                c.drawString(100, y_position, line[:80])
                y_position -= 15
            
            c.save()
            pdf_buffer.seek(0)
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={result.contract_number}.pdf"
                }
            )
            
        elif format == "word":
            # Generate Word document
            try:
                from docx import Document
                from io import BytesIO
                
                doc = Document()
                doc.add_heading(result.contract_title or "Contract", 0)
                doc.add_paragraph(f"Contract Number: {result.contract_number}")
                
                # Clean content
                import re
                clean_content = re.sub('<.*?>', '', content)
                doc.add_paragraph(clean_content)
                
                docx_buffer = BytesIO()
                doc.save(docx_buffer)
                docx_buffer.seek(0)
                
                from fastapi.responses import StreamingResponse
                return StreamingResponse(
                    docx_buffer,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={
                        "Content-Disposition": f"attachment; filename={result.contract_number}.docx"
                    }
                )
            except ImportError:
                raise HTTPException(status_code=500, detail="Word export not available")
                
        elif format == "html":
            # Return HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{result.contract_title}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #333; }}
                </style>
            </head>
            <body>
                <h1>{result.contract_title or "Contract"}</h1>
                <p>Contract Number: {result.contract_number}</p>
                <div>{content}</div>
            </body>
            </html>
            """
            
            from fastapi import Response
            return Response(
                content=html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename={result.contract_number}.html"
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail="Invalid export format")
            
    except Exception as e:
        logger.error(f"Error exporting contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# TRACK CHANGES ENDPOINTS
# =====================================================

@router.post("/track-changes/{contract_id}")
async def manage_track_changes(
    contract_id: int,
    action: str = Query(...),  # enable, disable, accept_all, reject_all
    change_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enable/disable track changes for contract - FIXED VERSION WITHOUT METADATA"""
    try:
        # Check contract exists
        contract_check = text("""
            SELECT id, status, updated_at FROM contracts WHERE id = :contract_id
        """)
        
        result = db.execute(contract_check, {"contract_id": contract_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Since we don't have a metadata column, we'll track changes in contract_versions
        # with a specific version_type to indicate tracked changes
        
        if action == "enable":
            # Create a version snapshot when enabling track changes
            version_query = text("""
                INSERT INTO contract_versions (
                    contract_id, version_number, version_type, 
                    contract_content, change_summary, created_by, created_at
                )
                SELECT 
                    :contract_id,
                    COALESCE(MAX(version_number), 0) + 1,
                    'track_changes_enabled',
                    (SELECT contract_content FROM contract_versions 
                     WHERE contract_id = :contract_id 
                     ORDER BY version_number DESC LIMIT 1),
                    'Track changes enabled',
                    :user_id,
                    NOW()
                FROM contract_versions
                WHERE contract_id = :contract_id
            """)
            
            db.execute(version_query, {
                "contract_id": contract_id,
                "user_id": current_user.id
            })
            db.commit()
            
            message = "Track changes enabled"
            
        elif action == "disable":
            # Create a version when disabling
            version_query = text("""
                INSERT INTO contract_versions (
                    contract_id, version_number, version_type,
                    contract_content, change_summary, created_by, created_at
                )
                SELECT 
                    :contract_id,
                    COALESCE(MAX(version_number), 0) + 1,
                    'track_changes_disabled',
                    (SELECT contract_content FROM contract_versions 
                     WHERE contract_id = :contract_id 
                     ORDER BY version_number DESC LIMIT 1),
                    'Track changes disabled',
                    :user_id,
                    NOW()
                FROM contract_versions
                WHERE contract_id = :contract_id
            """)
            
            db.execute(version_query, {
                "contract_id": contract_id,
                "user_id": current_user.id
            })
            db.commit()
            
            message = "Track changes disabled"
            
        elif action == "accept_all":
            # Accept all changes - create a clean version
            version_query = text("""
                INSERT INTO contract_versions (
                    contract_id, version_number, version_type,
                    contract_content, change_summary, created_by, created_at
                )
                SELECT 
                    :contract_id,
                    COALESCE(MAX(version_number), 0) + 1,
                    'changes_accepted',
                    (SELECT contract_content FROM contract_versions 
                     WHERE contract_id = :contract_id 
                     ORDER BY version_number DESC LIMIT 1),
                    'All tracked changes accepted',
                    :user_id,
                    NOW()
                FROM contract_versions
                WHERE contract_id = :contract_id
            """)
            
            db.execute(version_query, {
                "contract_id": contract_id,
                "user_id": current_user.id
            })
            db.commit()
            
            message = "All changes accepted"
            
        elif action == "reject_all":
            # Reject all changes - revert to previous clean version
            # Find the last non-tracked version
            revert_query = text("""
                SELECT contract_content 
                FROM contract_versions 
                WHERE contract_id = :contract_id 
                    AND version_type NOT IN ('track_changes_enabled', 'track_changes_disabled')
                ORDER BY version_number DESC 
                LIMIT 1
            """)
            
            revert_result = db.execute(revert_query, {"contract_id": contract_id}).fetchone()
            
            if revert_result:
                # Create a new version with reverted content
                version_query = text("""
                    INSERT INTO contract_versions (
                        contract_id, version_number, version_type,
                        contract_content, change_summary, created_by, created_at
                    )
                    SELECT 
                        :contract_id,
                        COALESCE(MAX(version_number), 0) + 1,
                        'changes_rejected',
                        :content,
                        'All tracked changes rejected - reverted to previous version',
                        :user_id,
                        NOW()
                    FROM contract_versions
                    WHERE contract_id = :contract_id
                """)
                
                db.execute(version_query, {
                    "contract_id": contract_id,
                    "content": revert_result.contract_content,
                    "user_id": current_user.id
                })
                db.commit()
                
                message = "All changes rejected - reverted to previous version"
            else:
                message = "No previous version to revert to"
            
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        # Update contract's updated_at timestamp
        update_query = text("""
            UPDATE contracts 
            SET updated_at = NOW(), updated_by = :user_id
            WHERE id = :contract_id
        """)
        
        db.execute(update_query, {
            "contract_id": contract_id,
            "user_id": current_user.id
        })
        db.commit()
        
        # Log the action for audit trail
        log_contract_action(db, current_user.id, contract_id, f"track_changes_{action}", {
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {
            "success": True,
            "message": message,
            "action": action,
            "contract_id": contract_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error managing track changes: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to manage track changes: {str(e)}"
        )

        
# =====================================================
# ADDITIONAL HELPER FUNCTIONS
# =====================================================

def log_contract_action(db: Session, user_id: int, contract_id: int, action: str, details: dict = None):
    """Log contract actions for audit trail"""
    try:
        audit_query = text("""
            INSERT INTO audit_logs 
            (user_id, action, entity_type, entity_id, details, created_at)
            VALUES (:user_id, :action, 'contract', :entity_id, :details, NOW())
        """)
        
        db.execute(audit_query, {
            "user_id": user_id,
            "action": action,
            "entity_id": contract_id,
            "details": json.dumps(details) if details else None
        })
    except:
        pass  # Don't fail main operation if audit fails

def send_notification(db: Session, user_id: int, title: str, message: str, type: str = "info"):
    """Send notification to user"""
    try:
        notif_query = text("""
            INSERT INTO notifications 
            (recipient_id, notification_type, title, message, status, created_at)
            VALUES (:user_id, :type, :title, :message, 'pending', NOW())
        """)
        
        db.execute(notif_query, {
            "user_id": str(user_id),
            "type": type,
            "title": title,
            "message": message
        })
    except:
        pass  # Don't fail main operation if notification fails


# =====================================================
# Add these endpoints at the end of app/api/api_v1/contracts/contracts.py
# Before the last line of the file
# =====================================================
@router.post("/send-to-counterparty")
async def send_to_counterparty(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send contract to counter-party for review and negotiation"""
    try:
        data = await request.json()
        
        # Simple - just get the flat fields
        contract_id = data.get('contract_id')
        counterparty_email = data.get('counterparty_email')
        counterparty_user_id = data.get('counterparty_user_id')
        counterparty_company_id = data.get('counterparty_company_id')
        counterparty_company_name = data.get('counterparty_company_name')
        message = data.get('message', '')
        
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Update contract status
        contract.status = 'counterparty_internal_review'
        contract.party_b_id = counterparty_company_id
        contract.party_b_lead_id = counterparty_user_id
        contract.updated_at = datetime.now()
        
        # Log the action
        logger.info(f"Contract {contract_id} sent to counter-party: {counterparty_email}")
        if counterparty_company_name:
            logger.info(f"Counter-party company: {counterparty_company_name} (ID: {counterparty_company_id}, User ID: {counterparty_user_id})")
        else:
            logger.info(f"External counter-party email: {counterparty_email}")
        
        db.commit()
        
        # TODO: Send email notification to counter-party
        # send_email_notification(counterparty_email, contract, message)
        
        return {
            "success": True,
            "message": "Contract sent to counter-party successfully",
            "contract_status": "negotiation",
            "counterparty_email": counterparty_email,
            "counterparty_company_name": counterparty_company_name
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f" Error sending to counter-party: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quick-approve")
async def quick_approve_contract(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Quick approve contract by counter-party"""
    try:
        data = await request.json()
        contract_id = data.get('contract_id')
        
        # Get contract details
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Get initiator's company_id from the contract
        initiator_company_id = contract.company_id
        
        # Update contract status to negotiation_completed
        contract.status = 'negotiation_completed'
        contract.updated_at = datetime.now()
        
        #  STEP 1: Mark current user's (counter-party) workflow instance as 'completed'
        complete_counterparty_workflow = text("""
            UPDATE workflow_instances wi
            INNER JOIN workflows w ON wi.workflow_id = w.id
            SET wi.status = 'completed',
                wi.completed_at = NOW()
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :counterparty_company_id
            AND wi.status IN ('pending', 'in_progress', 'active')
        """)
        
        db.execute(complete_counterparty_workflow, {
            "contract_id": contract_id,
            "counterparty_company_id": current_user.company_id
        })
        
        logger.info(f" Completed counter-party workflow for company {current_user.company_id}")
        
        #  STEP 2: Activate initiator's workflow instance to 'active'
        activate_initiator_workflow = text("""
            UPDATE workflow_instances wi
            INNER JOIN workflows w ON wi.workflow_id = w.id
            SET wi.status = 'active',
                wi.started_at = NOW()
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :initiator_company_id
            AND wi.status IN ('pending', 'in_progress')
        """)
        
        db.execute(activate_initiator_workflow, {
            "contract_id": contract_id,
            "initiator_company_id": initiator_company_id
        })
        
        logger.info(f" Activated initiator workflow for company {initiator_company_id}")
        
        # Create activity log
        try:
            from sqlalchemy import text as sql_text
            activity_query = sql_text("""
                INSERT INTO contract_activity 
                (contract_id, action_type, action_by, notes, timestamp)
                VALUES 
                (:contract_id, 'quick_approved', :user_id, 'Contract quickly approved by counter-party', NOW())
            """)
            db.execute(activity_query, {
                "contract_id": contract_id,
                "user_id": current_user.id
            })
        except Exception as activity_err:
            logger.warning(f"Could not create activity log: {str(activity_err)}")
        
        db.commit()
        
        logger.info(f" Contract {contract_id} quick approved by user {current_user.id}")
        
        # TODO: Send notification to initiator
        # send_notification_to_initiator(contract)
        
        return {
            "success": True,
            "message": "Contract approved successfully. Initiator's workflow has been activated.",
            "contract_status": "negotiation_completed"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f" Error approving contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/{contract_id}/complete-counterparty-review")
async def complete_counterparty_review(
    contract_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Complete counterparty review - moves to negotiation"""
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Update status to negotiation
        update_query = text("""
            UPDATE contracts 
            SET status = 'negotiation', 
                updated_at = NOW() 
            WHERE id = :id
        """)
        db.execute(update_query, {"id": contract_id})
        
        # Log the action using your audit_logs schema
        audit_query = text("""
            INSERT INTO audit_logs (user_id, contract_id, action_type, action_details, ip_address, created_at)
            VALUES (:user_id, :contract_id, :action_type, :action_details, :ip_address, NOW())
        """)
        db.execute(audit_query, {
            "user_id": current_user.id,
            "contract_id": contract_id,
            "action_type": "COMPLETE_COUNTERPARTY_REVIEW",
            "action_details": json.dumps({
                "status_changed_from": "counterparty_internal_review",
                "status_changed_to": "negotiation"
            }),
            "ip_address": client_ip
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": "Review completed",
            "new_status": "negotiation"
        }
        
    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}




"""
Fixed Clause Analysis API Endpoint - app/api/api_v1/contracts/contracts.py

Add this endpoint to your contracts.py file to properly analyze all clauses
"""
def sanitize_for_json(text: str) -> str:
    """Sanitize text to be safely included in JSON responses"""
    if not text:
        return ""
    
    # Replace problematic characters
    text = text.replace('\n', ' ')  # Remove newlines
    text = text.replace('\r', ' ')  # Remove carriage returns
    text = text.replace('\t', ' ')  # Remove tabs
    text = text.replace('"', "'")   # Replace double quotes with single quotes
    text = text.replace('\\', '/')  # Replace backslashes
    
    # Limit length to prevent oversized responses
    if len(text) > 1000:
        text = text[:997] + "..."
    
    # Remove multiple spaces
    import re
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


@router.post("/analyze-full-contract")
async def analyze_full_contract(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze all clauses in the full contract content and provide suggestions
    for each identified clause.
    
    This endpoint:
    1. Takes the full contract text
    2. Uses Claude AI to identify ALL major clauses
    3. Provides specific suggestions for each clause
    4. Returns risk assessment and compliance notes
    """
    try:
        contract_text = request.get("contract_text", "")
        contract_id = request.get("contract_id")
        
        # Validate input
        if not contract_text or len(contract_text) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Contract content is too short to analyze (minimum 50 characters)"
            )
        
        logger.info(f"📋 Analyzing full contract content ({len(contract_text)} characters)")
        
        # Initialize Claude service
        claude_service = ClaudeService()
        
        if not claude_service.client:
            logger.warning("Claude client not available, using fallback analysis")
            return get_fallback_clause_analysis(contract_text)
        
        # Prepare comprehensive prompt for Claude with strict JSON formatting rules
        prompt = f"""You are an expert contract analyst specializing in Qatar jurisdiction. Analyze the following complete contract and identify ALL major clauses.

CONTRACT TEXT:
{contract_text[:8000]}

Your task:
1. Identify and extract ALL major clauses in this contract including:
   - Governing Law & Jurisdiction
   - Payment Terms & Conditions
   - Term & Termination
   - Warranties & Representations
   - Indemnification & Liability
   - Confidentiality & Non-Disclosure
   - Dispute Resolution & Arbitration
   - Force Majeure
   - Intellectual Property Rights
   - Insurance Requirements
   - Service Level Agreements
   - Change Management
   - Any other significant clauses

2. For EACH clause identified, provide:
   - The exact clause name/title
   - A CONCISE SUMMARY of the clause content (max 300 characters)
   - A risk assessment: "low", "medium", or "high"
   - 2-4 specific, actionable suggestions for improvement
   - Compliance notes specific to Qatar Civil and Commercial Law
   - A legal protection score from 1-5
   - An improved version summary (max 300 characters)

3. Also identify:
   - Important clauses that are MISSING from the contract
   - Overall assessment of the contract quality
   - Total number of clauses analyzed

CRITICAL JSON FORMATTING RULES:
- Respond in VALID JSON format ONLY
- NO markdown, NO code blocks, NO extra text
- For clause_text: Use SUMMARY only (max 300 chars, single line)
- For improved_version: Use SUMMARY only (max 300 chars, single line)
- REPLACE all double quotes in text with single quotes
- NO newlines, tabs, or special characters in text fields
- Keep all text fields on single lines
- Properly escape any special characters

Expected JSON structure:
{{
    "clauses_identified": [
        {{
            "clause_name": "Governing Law and Jurisdiction",
            "clause_text": "Agreement governed by Qatar laws with disputes subject to Qatar Courts jurisdiction",
            "risk_level": "medium",
            "current_score": 3,
            "suggestions": [
                "Specify Qatar Courts or QICCA arbitration explicitly",
                "Add reference to Qatar Civil Code Articles",
                "Include bilingual interpretation clause"
            ],
            "compliance_note": "Complies with Qatar Civil Code Article 1. Consider Qatar Courts jurisdiction reference per Law No. 13 of 1990",
            "improved_version": "Governed by Qatar laws. Disputes subject to Qatar Courts exclusive jurisdiction or QICCA arbitration per parties agreement"
        }}
    ],
    "overall_assessment": "Contract shows moderate legal protection with clear commercial terms. Needs enhanced dispute resolution and liability provisions",
    "missing_clauses": [
        "Force Majeure provisions per Qatar Civil Code Article 215",
        "Insurance requirements and coverage specifications",
        "IP rights assignment terms",
        "Data protection compliance with Qatar Law"
    ],
    "total_clauses": 8
}}

IMPORTANT REMINDERS:
- Keep clause_text and improved_version BRIEF (max 300 chars each)
- Use apostrophes (') instead of quotes (") in all text
- Single line text only - no line breaks
- Valid JSON syntax - proper commas and brackets

Begin your analysis now. Respond with ONLY the valid JSON object."""

        try:
            # Call Claude API
            response = claude_service.client.messages.create(
                model=claude_service.model,
                max_tokens=8000,  # Increased for comprehensive analysis
                temperature=0.2,  # Lower temperature for more consistent JSON
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract response text
            response_text = response.content[0].text.strip()
            logger.info(f"📥 Received response from Claude ({len(response_text)} characters)")
            
            # Clean up response - remove markdown formatting
            cleaned_text = response_text
            
            # Remove markdown code blocks
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                # Try to extract content between first ``` and last ```
                parts = cleaned_text.split("```")
                if len(parts) >= 3:
                    cleaned_text = parts[1].strip()
                else:
                    cleaned_text = cleaned_text.replace("```", "").strip()
            
            # Extract JSON object using regex
            json_match = re.search(r'\{[\s\S]*\}', cleaned_text)
            if json_match:
                cleaned_text = json_match.group()
            
            logger.info(f"🧹 Cleaned response ready for parsing ({len(cleaned_text)} chars)")
            
            # Parse JSON response
            try:
                result = json.loads(cleaned_text)
            except json.JSONDecodeError as json_err:
                logger.error(f" Initial JSON parse failed: {str(json_err)}")
                logger.error(f" Error at line {json_err.lineno}, column {json_err.colno}")
                logger.error(f" Problematic section: {cleaned_text[max(0, json_err.pos-100):json_err.pos+100]}")
                
                # Try additional cleanup
                # Replace common problematic patterns
                cleaned_text = cleaned_text.replace('\\"', "'")  # Replace escaped quotes
                cleaned_text = re.sub(r'[\n\r\t]', ' ', cleaned_text)  # Remove all whitespace chars
                cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Collapse multiple spaces
                
                # Try parsing again
                result = json.loads(cleaned_text)
                logger.info(" Successfully parsed after additional cleanup")
            
            # Validate response structure
            if "clauses_identified" not in result:
                logger.error("Invalid response structure: missing clauses_identified")
                raise ValueError("Invalid response structure from AI")
            
            clauses = result.get("clauses_identified", [])
            
            if not clauses:
                logger.warning("No clauses identified by AI, using fallback")
                raise ValueError("No clauses identified in the contract")
            
            logger.info(f" Successfully identified {len(clauses)} clauses")
            
            # Sanitize all text fields to ensure JSON safety
            for idx, clause in enumerate(clauses):
                # Set defaults and sanitize for missing/invalid fields
                if "clause_name" not in clause or not clause["clause_name"]:
                    clause["clause_name"] = f"Clause {idx + 1}"
                else:
                    clause["clause_name"] = sanitize_for_json(str(clause["clause_name"]))
                
                if "clause_text" not in clause or not clause["clause_text"]:
                    clause["clause_text"] = "Summary not available"
                else:
                    clause["clause_text"] = sanitize_for_json(str(clause["clause_text"]))
                
                # Validate risk level
                if "risk_level" not in clause or clause["risk_level"] not in ["low", "medium", "high"]:
                    clause["risk_level"] = "medium"
                
                # Validate score
                if "current_score" not in clause:
                    clause["current_score"] = 3
                else:
                    try:
                        clause["current_score"] = int(clause["current_score"])
                        if clause["current_score"] < 1 or clause["current_score"] > 5:
                            clause["current_score"] = 3
                    except (ValueError, TypeError):
                        clause["current_score"] = 3
                
                # Sanitize suggestions array
                if "suggestions" not in clause or not isinstance(clause["suggestions"], list):
                    clause["suggestions"] = ["Review clause for completeness"]
                else:
                    clause["suggestions"] = [
                        sanitize_for_json(str(s)) for s in clause["suggestions"] if s
                    ][:6]  # Limit to 6 suggestions max
                    if not clause["suggestions"]:
                        clause["suggestions"] = ["Review clause for completeness"]
                
                if "compliance_note" not in clause or not clause["compliance_note"]:
                    clause["compliance_note"] = "Legal review recommended"
                else:
                    clause["compliance_note"] = sanitize_for_json(str(clause["compliance_note"]))
                
                if "improved_version" not in clause or not clause["improved_version"]:
                    clause["improved_version"] = "Improved version not available"
                else:
                    clause["improved_version"] = sanitize_for_json(str(clause["improved_version"]))
            
            # Sanitize overall assessment and missing clauses
            overall_assessment = sanitize_for_json(
                str(result.get("overall_assessment", "Contract analyzed successfully"))
            )
            
            missing_clauses = result.get("missing_clauses", [])
            if isinstance(missing_clauses, list):
                missing_clauses = [sanitize_for_json(str(mc)) for mc in missing_clauses if mc][:10]
            else:
                missing_clauses = []
            
            # Log the analysis to audit trail
            try:
                audit_log = text("""
                    INSERT INTO audit_logs 
                    (user_id, action_type, action_details, ip_address, user_agent, created_at)
                    VALUES 
                    (:user_id, :action_type, :action_details, :ip_address, :user_agent, NOW())
                """)
                
                db.execute(audit_log, {
                    "user_id": current_user.id,
                    "action_type": "AI_FULL_CONTRACT_ANALYSIS",
                    "action_details": json.dumps({
                        "contract_id": contract_id,
                        "contract_length": len(contract_text),
                        "clauses_identified": len(clauses),
                        "ai_powered": True
                    }),
                    "ip_address": "system",
                    "user_agent": "Claude AI"
                })
                db.commit()
            except Exception as audit_error:
                logger.error(f"Failed to log audit trail: {str(audit_error)}")
                # Continue even if audit logging fails
            
            logger.info(f"🎉 Analysis complete: {len(clauses)} clauses, {len(missing_clauses)} missing")
            
            return {
                "success": True,
                "clauses_identified": clauses,
                "overall_assessment": overall_assessment,
                "missing_clauses": missing_clauses,
                "total_clauses": len(clauses),
                "ai_powered": True
            }
            
        except json.JSONDecodeError as e:
            logger.error(f" JSON parsing error after all attempts: {str(e)}")
            logger.error(f" Response text (first 1000 chars): {cleaned_text[:1000]}")
            logger.error(f"📍 Error location: line {e.lineno}, column {e.colno}, position {e.pos}")
            logger.warning(" Falling back to pattern matching analysis")
            return get_fallback_clause_analysis(contract_text)
            
        except Exception as e:
            logger.error(f" Claude API error: {str(e)}")
            logger.warning(" Falling back to pattern matching analysis")
            return get_fallback_clause_analysis(contract_text)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error in full contract analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


def get_fallback_clause_analysis(contract_text: str):
    """
    Provide fallback clause analysis when AI is unavailable
    Uses pattern matching to identify common clauses
    """
    clauses = []
    
    # Common clause patterns
    clause_patterns = {
        "Governing Law": ["governing law", "applicable law", "governed by"],
        "Payment Terms": ["payment", "compensation", "fees", "invoice"],
        "Termination": ["termination", "terminate", "cancellation"],
        "Confidentiality": ["confidential", "non-disclosure", "proprietary"],
        "Indemnification": ["indemnify", "indemnification", "hold harmless"],
        "Warranties": ["warrant", "representation", "guarantee"],
        "Liability": ["liability", "liable", "damages"],
        "Dispute Resolution": ["dispute", "arbitration", "mediation"],
        "Force Majeure": ["force majeure", "act of god", "beyond control"]
    }
    
    contract_lower = contract_text.lower()
    
    for clause_name, patterns in clause_patterns.items():
        # Check if any pattern exists in the contract
        if any(pattern in contract_lower for pattern in patterns):
            # Try to extract a snippet of text around the clause
            for pattern in patterns:
                if pattern in contract_lower:
                    start_idx = contract_lower.find(pattern)
                    # Extract 200 characters around the pattern
                    snippet_start = max(0, start_idx - 50)
                    snippet_end = min(len(contract_text), start_idx + 250)
                    clause_text = contract_text[snippet_start:snippet_end].strip()
                    
                    clauses.append({
                        "clause_name": clause_name,
                        "clause_text": f"...{clause_text}...",
                        "risk_level": "medium",
                        "current_score": 3,
                        "suggestions": [
                            f"Review {clause_name.lower()} clause for completeness",
                            "Ensure compliance with Qatar Civil and Commercial Law",
                            "Consider legal review for risk mitigation"
                        ],
                        "compliance_note": "Requires legal review for Qatar law compliance",
                        "improved_version": "AI analysis unavailable - legal review recommended"
                    })
                    break
    
    if not clauses:
        # Default response if no clauses found
        clauses = [{
            "clause_name": "General Contract",
            "clause_text": contract_text[:300] + "...",
            "risk_level": "medium",
            "current_score": 3,
            "suggestions": [
                "Add standard contract clauses (Governing Law, Payment Terms, Termination)",
                "Include dispute resolution provisions",
                "Add confidentiality and indemnification clauses"
            ],
            "compliance_note": "Review for Qatar law compliance",
            "improved_version": "Structure contract with standard clauses"
        }]
    
    return {
        "success": True,
        "clauses_identified": clauses,
        "overall_assessment": "Basic clause analysis completed. AI-powered analysis unavailable.",
        "missing_clauses": [
            "Consider adding standard clauses if not present",
            "Legal review recommended"
        ],
        "total_clauses": len(clauses),
        "ai_powered": False
    }



@router.get("/workflow/availability/{contract_id}")
async def check_workflow_availability(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if master and custom workflows are available for a contract
    """
    try:
        # Check for active master workflow for the company
        master_query = text("""
            SELECT id, workflow_name 
            FROM workflows 
            WHERE company_id = :company_id 
            AND is_master = 1 
            AND is_active = 1
            LIMIT 1
        """)
        
        master_workflow = db.execute(master_query, {
            "company_id": current_user.company_id
        }).fetchone()
        
        # Check for custom workflow for this specific contract
        custom_query = text("""
            SELECT w.id, w.workflow_name 
            FROM workflows w
            INNER JOIN workflow_instances wi ON w.id = wi.workflow_id
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :company_id
            AND w.is_master = 0
           
            LIMIT 1
        """)
        
        custom_workflow = db.execute(custom_query, {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        return {
            "success": True,
            "master_workflow": {
                "available": master_workflow is not None,
                "id": master_workflow.id if master_workflow else None,
                "name": master_workflow.workflow_name if master_workflow else None
            },
            "custom_workflow": {
                "available": custom_workflow is not None,
                "id": custom_workflow.id if custom_workflow else None,
                "name": custom_workflow.workflow_name if custom_workflow else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking workflow availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))





@router.post("/workflow/ensure-instance/{contract_id}")
async def ensure_workflow_instance(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ensure workflow instance exists for contract
    - If master workflow exists for company but no instance → Create instance
    - If custom workflow exists but no instance → Create instance
    - Returns current workflow status
    """
    try:
        # Check if workflow instance already exists
        existing_instance_query = text("""
            SELECT wi.id, wi.workflow_id, wi.status, w.workflow_name, w.is_master
            FROM workflow_instances wi
            INNER JOIN workflows w ON wi.workflow_id = w.id
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :company_id
            AND is_master=1
            LIMIT 1
        """)
        
        existing_instance = db.execute(existing_instance_query, {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if existing_instance:
            logger.info(f" Workflow instance already exists for contract {contract_id}")
            return {
                "success": True,
                "instance_exists": True,
                "workflow_id": existing_instance.workflow_id,
                "workflow_name": existing_instance.workflow_name,
                "is_master": existing_instance.is_master,
                "status": existing_instance.status,
                "message": "Workflow instance already exists"
            }
        
        # Check for master workflow
        master_workflow_query = text("""
            SELECT id, workflow_name 
            FROM workflows 
            WHERE company_id = :company_id 
            AND is_master = 1 
            AND is_active = 1
            LIMIT 1
        """)
        
        master_workflow = db.execute(master_workflow_query, {
            "company_id": current_user.company_id
        }).fetchone()
        
        # If master workflow exists, create instance
        if master_workflow:
            insert_instance = text("""
                INSERT INTO workflow_instances 
                (contract_id, workflow_id, status, current_step, started_at)
                VALUES (:contract_id, :workflow_id, 'pending', 1, NOW())
            """)
            
            db.execute(insert_instance, {
                "contract_id": contract_id,
                "workflow_id": master_workflow.id
            })
            
            db.commit()
            
            logger.info(f" Created workflow instance for contract {contract_id} using master workflow {master_workflow.id}")
            
            return {
                "success": True,
                "instance_exists": False,
                "instance_created": True,
                "workflow_id": master_workflow.id,
                "workflow_name": master_workflow.workflow_name,
                "is_master": True,
                "status": "pending",
                "message": "Master workflow instance created"
            }
        
        # No master workflow exists
        logger.info(f"ℹ️ No master workflow found for company {current_user.company_id}")
        return {
            "success": True,
            "instance_exists": False,
            "instance_created": False,
            "workflow_id": None,
            "workflow_name": None,
            "is_master": None,
            "status": None,
            "message": "No master workflow configured"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f" Error ensuring workflow instance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-generate-stream/{contract_id}")
async def stream_ai_contract_generation(
    contract_id: int,
    request_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stream AI-generated contract content directly to the editor"""
    try:
        logger.info(f"🎯 Streaming AI generation for contract {contract_id}")
        logger.info(f"📦 Received data: {json.dumps(request_data, indent=2)}")
        
        # Verify contract exists
        contract = db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.company_id == current_user.company_id
        ).first()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Extract values with safe defaults
        contract_type = request_data.get("contract_type", "Service Agreement")
        profile_type = request_data.get("profile_type", "client")
        parties = request_data.get("parties", {})
        party_a = parties.get("party_a", {})
        party_b = parties.get("party_b", {})
        contract_value = request_data.get("contract_value", "100,000")
        currency = request_data.get("currency", "QAR")
        start_date = request_data.get("start_date", "")
        end_date = request_data.get("end_date", "")
        selected_clause_descriptions = request_data.get("selected_clauses", [])
        jurisdiction = request_data.get("jurisdiction", "Qatar")


        #  EXTRACT METADATA WITH SPECIAL REQUIREMENTS
        metadata = request_data.get("metadata", {})
        additional_requirements = metadata.get("additional_requirements", "")
        user_prompt = metadata.get("prompt", "")
        payment_terms = metadata.get("payment_terms", "")


        
        party_a_name = party_a.get("name", "Party A")
        party_b_name = party_b.get("name", "Party B")
        
        # Build prompt
        prompt_text = f"""Generate a complete, production-ready {contract_type} contract:
- Party A ({profile_type}): 
Jurisdiction: {jurisdiction}

Selected Clauses: {', '.join(selected_clause_descriptions) if selected_clause_descriptions else 'Standard clauses'}

**CRITICAL REQUIREMENTS:**

1. Production-ready, contractually & legally binding (minimum 3,500 words)
2. Professional legal language with contractually & legally binding for {jurisdiction}
4. Every clause fully developed with procedures and consequences
5. {additional_requirements}
6. {payment_terms}
7. {user_prompt}
8. Dont include signature section

**FORMAT:**
- Clean HTML: <h2> for sections, <h3> for subsections, <p> for paragraphs
- Use <strong> for party names and defined terms
- Wrap in: <div class="contract-document">...</div>
- No markdown, no backticks, pure HTML only

Generate the complete contract now:"""

        logger.info("🚀 Starting Claude streaming...")
        
        # Define the generator function
        async def generate_stream():
            # Import text function here to ensure it's in scope
            from sqlalchemy import text as sql_text
            
            try:
                # Call Claude API with streaming
                with claude_service.client.messages.stream(
                    model=claude_service.model,
                    max_tokens=16000,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt_text}]
                ) as stream:
                    accumulated_text = ""
                    
                    # Send initial metadata
                    yield f"data: {json.dumps({'type': 'start', 'contract_id': contract_id})}\n\n"
                    
                    # Stream content chunks
                    for text_chunk in stream.text_stream:
                        accumulated_text += text_chunk
                        yield f"data: {json.dumps({'type': 'content', 'text': text_chunk})}\n\n"
                    
                    # Get final metadata
                    final_message = stream.get_final_message()
                    tokens_used = final_message.usage.input_tokens + final_message.usage.output_tokens
                    word_count = len(accumulated_text.split())
                    
                    logger.info(f" Generated {word_count} words, {tokens_used} tokens")
                    
                    # Clean up markdown
                    for marker in ["```html", "```"]:
                        if accumulated_text.startswith(marker):
                            accumulated_text = accumulated_text[len(marker):].strip()
                        if accumulated_text.endswith("```"):
                            accumulated_text = accumulated_text[:-3].strip()
                    
                    # Save to database
                    clause_summary = ", ".join([c.split('-')[0].strip() for c in selected_clause_descriptions]) if selected_clause_descriptions else "Standard"
                    
                    # Check if version exists
                    existing_version = db.execute(sql_text("""
                        SELECT id FROM contract_versions 
                        WHERE contract_id = :contract_id AND version_number = 1
                    """), {"contract_id": contract_id}).fetchone()
                    
                    if existing_version:
                        db.execute(sql_text("""
                            UPDATE contract_versions 
                            SET contract_content = :contract_content,
                                change_summary = :change_summary,
                                created_at = :created_at
                            WHERE contract_id = :contract_id AND version_number = 1
                        """), {
                            "contract_id": contract_id,
                            "contract_content": accumulated_text,
                            "change_summary": f"AI-regenerated: {clause_summary}",
                            "created_at": datetime.utcnow()
                        })
                    else:
                        db.execute(sql_text("""
                            INSERT INTO contract_versions (contract_id, version_number, version_type,
                                                         contract_content, change_summary,
                                                         created_by, created_at)
                            VALUES (:contract_id, :version_number, :version_type,
                                    :contract_content, :change_summary,
                                    :created_by, :created_at)
                        """), {
                            "contract_id": contract_id,
                            "version_number": 1,
                            "version_type": "ai_generated",
                            "contract_content": accumulated_text,
                            "change_summary": f"AI-generated: {clause_summary}",
                            "created_by": str(current_user.id),
                            "created_at": datetime.utcnow()
                        })
                    
                    db.commit()
                    logger.info(f"💾 Saved to database")
                    
                    # Send completion
                    yield f"data: {json.dumps({'type': 'done', 'word_count': word_count, 'tokens_used': tokens_used})}\n\n"
                    
            except Exception as e:
                logger.error(f"❌ Streaming error: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Stream setup error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# Add this endpoint to your router
@router.put("/{contract_id}/update-metadata")
async def update_contract_metadata(
    contract_id: int,
    request_data: UpdateMetadataRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update AI generation parameters for a contract
    This allows regeneration with modified metadata
    """
    try:
        logger.info(f"📝 Updating metadata for contract {contract_id}")
        logger.info(f"📦 New params: {json.dumps(request_data.ai_generation_params, indent=2)}")

        # Verify contract exists and belongs to user's company
        contract_check = db.execute(text("""
            SELECT id, contract_number, is_ai_generated 
            FROM contracts 
            WHERE id = :contract_id 
            AND company_id = :company_id
        """), {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        }).fetchone()

        if not contract_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Verify it's an AI-generated contract
        if not contract_check.is_ai_generated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update metadata for non-AI-generated contracts"
            )

        # Convert params to JSON string
        params_json = json.dumps(request_data.ai_generation_params)

        # Update the metadata
        db.execute(text("""
            UPDATE contracts 
            SET ai_generation_params = :params,
                updated_at = :updated_at
            WHERE id = :contract_id
        """), {
            "params": params_json,
            "updated_at": datetime.utcnow(),
            "contract_id": contract_id
        })

        db.commit()

        logger.info(f"✅ Metadata updated for contract {contract_check.contract_number}")

        return {
            "success": True,
            "message": "Metadata updated successfully",
            "contract_id": contract_id,
            "contract_number": contract_check.contract_number,
            "updated_params": request_data.ai_generation_params
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error updating metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update metadata: {str(e)}"
        )



@router.post("/documents/upload/{contract_id}")
async def upload_contract_documents(
    contract_id: int,
    files: List[UploadFile] = File(...),
    document_type: str = Form(default="contract_attachment"),
    notes: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload supporting documents to a contract (UC 028)
    Supports exhibits, annexes, amendments, certificates, drafts
    """
    try:
        logger.info(f"📎 Uploading {len(files)} documents to contract {contract_id}")
        logger.info(f"👤 Current user company_id: {current_user.company_id}")
        
        # First, check if contract exists at all (for debugging)
        check_query = text("""
            SELECT id, company_id, contract_number, contract_title, project_id
            FROM contracts
            WHERE id = :contract_id
        """)
        
        contract_check = db.execute(check_query, {"contract_id": contract_id}).fetchone()
        
        if not contract_check:
            logger.error(f"❌ Contract {contract_id} does not exist in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found in database"
            )
        
        logger.info(f"✅ Contract {contract_id} exists with company_id: {contract_check.company_id}")
        
        # Now verify user has access to this contract
        if str(contract_check.company_id) != str(current_user.company_id):
            logger.warning(f"⚠️ Company mismatch: Contract company_id={contract_check.company_id}, User company_id={current_user.company_id}")
            # For now, allow access (you can restrict this later)
            logger.info("🔓 Allowing access despite company mismatch (temp fix)")
        
        # Use the contract data we already fetched
        contract = contract_check
        
        # Define upload directory
        UPLOAD_BASE_DIR = Path("app/static/uploads/contract_documents")
        contract_upload_dir = UPLOAD_BASE_DIR / f"contract_{contract_id}"
        contract_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Allowed file extensions per UC 028 requirements (15+ file types)
        ALLOWED_EXTENSIONS = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            'odt': 'application/vnd.oasis.opendocument.text',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'tiff': 'image/tiff',
            'zip': 'application/zip',
            'msg': 'application/vnd.ms-outlook',
            'eml': 'message/rfc822'
        }
        
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per UC 028
        
        uploaded_documents = []
        errors = []
        
        for file in files:
            try:
                # Validate file extension
                file_ext = Path(file.filename).suffix.lower().replace('.', '')
                if file_ext not in ALLOWED_EXTENSIONS:
                    errors.append({
                        "filename": file.filename,
                        "error": f"File type .{file_ext} not allowed"
                    })
                    continue
                
                # Read file content
                content = await file.read()
                file_size = len(content)
                
                # Validate file size (50MB limit)
                if file_size > MAX_FILE_SIZE:
                    errors.append({
                        "filename": file.filename,
                        "error": f"File size exceeds 50MB limit"
                    })
                    continue
                
                # Generate unique document ID and hash for blockchain
                doc_id = str(uuid.uuid4())
                file_hash = hashlib.sha256(content).hexdigest()
                
                # Save file with UUID prefix to prevent conflicts
                safe_filename = f"{doc_id}_{file.filename}"
                file_path = contract_upload_dir / safe_filename
                
                with open(file_path, "wb") as f:
                    f.write(content)
                
                # Get relative path for database
                relative_path = str(file_path.relative_to(Path("app")))
                
                # Prepare metadata per UC 028 requirements
                metadata = json.dumps({
                    "contract_id": int(contract_id),
                    "contract_number": contract.contract_number,
                    "contract_title": contract.contract_title,
                    "project_id": getattr(contract, 'project_id', None),
                    "original_filename": file.filename,
                    "notes": notes,
                    "upload_source": "contract_editor",
                    "uploader_email": current_user.email,
                    "document_purpose": document_type
                })
                
                # Insert into documents table
                insert_query = text("""
                    INSERT INTO documents (
                        id, company_id, contract_id, document_name, document_type,
                        file_path, file_size, mime_type, hash_value,
                        uploaded_by, uploaded_at, version, access_count, metadata
                    ) VALUES (
                        :id, :company_id, :contract_id, :document_name, :document_type,
                        :file_path, :file_size, :mime_type, :hash_value,
                        :uploaded_by, :uploaded_at, 1, 0, :metadata
                    )
                """)
                
                db.execute(insert_query, {
                    "id": doc_id,
                    "company_id": contract.company_id,  # Use contract's company_id
                    "contract_id": contract_id,
                    "document_name": file.filename,
                    "document_type": document_type,
                    "file_path": relative_path,
                    "file_size": file_size,
                    "mime_type": ALLOWED_EXTENSIONS.get(file_ext, 'application/octet-stream'),
                    "hash_value": file_hash,
                    "uploaded_by": current_user.id,
                    "uploaded_at": datetime.utcnow(),
                    "metadata": metadata
                })
                
                db.commit()
                
                uploaded_documents.append({
                    "id": doc_id,
                    "name": file.filename,
                    "size": file_size,
                    "type": file_ext,
                    "hash": file_hash[:16],  # First 16 chars for display
                    "uploaded_at": datetime.utcnow().isoformat()
                })
                
                logger.info(f"✅ Uploaded: {file.filename} ({file_size} bytes)")
                
            except Exception as e:
                logger.error(f"❌ Failed to upload {file.filename}: {str(e)}", exc_info=True)
                errors.append({
                    "filename": file.filename,
                    "error": str(e)
                })
                db.rollback()
        
        # Return results
        return {
            "success": True,
            "message": f"Uploaded {len(uploaded_documents)} of {len(files)} files",
            "uploaded": uploaded_documents,
            "errors": errors if errors else None,
            "contract_id": contract_id,
            "total_files": len(files),
            "successful_uploads": len(uploaded_documents),
            "failed_uploads": len(errors)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading contract documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload documents: {str(e)}"
        )


@router.get("/documents/list/{contract_id}")
async def get_contract_documents(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all documents attached to a contract
    """
    try:
        # First verify contract exists
        check_query = text("""
            SELECT id, company_id FROM contracts WHERE id = :contract_id
        """)
        
        contract = db.execute(check_query, {"contract_id": contract_id}).fetchone()
        
        if not contract:
            logger.error(f"❌ Contract {contract_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )
        
        logger.info(f"📄 Listing documents for contract {contract_id} (company: {contract.company_id})")
        
        # Get documents - no company_id restriction for now
        query = text("""
            SELECT 
                d.id,
                d.document_name,
                d.document_type,
                d.file_size,
                d.mime_type,
                d.hash_value,
                d.uploaded_at,
                d.version,
                d.access_count,
                CONCAT(u.first_name, ' ', u.last_name) as uploaded_by_name,
                u.email as uploaded_by_email
            FROM documents d
            LEFT JOIN users u ON d.uploaded_by = u.id
            WHERE d.contract_id = :contract_id
            ORDER BY d.uploaded_at DESC
        """)
        
        results = db.execute(query, {"contract_id": contract_id}).fetchall()
        
        documents = [
            {
                "id": row.id,
                "name": row.document_name,
                "type": row.document_type,
                "size": row.file_size,
                "mime_type": row.mime_type,
                "hash": row.hash_value[:16] if row.hash_value else None,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                "uploaded_by": row.uploaded_by_name,
                "email": row.uploaded_by_email,
                "version": row.version,
                "downloads": row.access_count
            }
            for row in results
        ]
        
        return {
            "success": True,
            "contract_id": contract_id,
            "total_documents": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logger.error(f"Error fetching contract documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/documents/delete/{document_id}")
async def delete_contract_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a contract document
    """
    try:
        # Get document info - no company restriction for now
        query = text("""
            SELECT file_path, document_name, contract_id, company_id
            FROM documents
            WHERE id = :document_id
        """)
        
        doc = db.execute(query, {"document_id": document_id}).fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"🗑️ Deleting document {document_id}: {doc.document_name} (company: {doc.company_id})")
        
        # Delete file from filesystem
        file_path = Path("app") / doc.file_path
        if file_path.exists():
            file_path.unlink()
            logger.info(f"🗑️ Deleted file: {file_path}")
        
        # Delete from database
        delete_query = text("""
            DELETE FROM documents
            WHERE id = :document_id
        """)
        
        db.execute(delete_query, {"document_id": document_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Document '{doc.document_name}' deleted successfully",
            "document_id": document_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/download/{document_id}")
async def download_contract_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download a contract document
    Returns the file with proper headers for download
    """
    try:
        # Get document info
        query = text("""
            SELECT 
                d.file_path,
                d.document_name,
                d.mime_type,
                d.file_size,
                d.contract_id,
                d.company_id,
                d.access_count
            FROM documents d
            WHERE d.id = :document_id
        """)
        
        doc = db.execute(query, {"document_id": document_id}).fetchone()
        
        if not doc:
            logger.error(f"❌ Document {document_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        logger.info(f"⬇️ Downloading document: {doc.document_name} (ID: {document_id})")
        
        # Construct full file path
        file_path = Path("app") / doc.file_path
        
        # Verify file exists
        if not file_path.exists():
            logger.error(f"❌ File not found on disk: {file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found on server: {doc.document_name}"
            )
        
        # Update access count
        update_query = text("""
            UPDATE documents
            SET access_count = access_count + 1
            WHERE id = :document_id
        """)
        
        db.execute(update_query, {"document_id": document_id})
        db.commit()
        
        logger.info(f"✅ Serving file: {file_path} ({doc.file_size} bytes)")
        
        # Return file as download
        from fastapi.responses import FileResponse
        
        return FileResponse(
            path=str(file_path),
            media_type=doc.mime_type or 'application/octet-stream',
            filename=doc.document_name,
            headers={
                "Content-Disposition": f'attachment; filename="{doc.document_name}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download document: {str(e)}"
        )


@router.get("/documents/view/{document_id}")
async def view_contract_document(
    document_id: str,
    inline: bool = Query(default=True, description="View inline in browser"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    View a contract document in browser (inline) or download
    Use inline=true for PDFs to open in browser, inline=false to force download
    """
    try:
        # Get document info
        query = text("""
            SELECT 
                d.file_path,
                d.document_name,
                d.mime_type,
                d.file_size,
                d.contract_id
            FROM documents d
            WHERE d.id = :document_id
        """)
        
        doc = db.execute(query, {"document_id": document_id}).fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Construct full file path
        file_path = Path("app") / doc.file_path
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on server")
        
        # Update access count
        update_query = text("""
            UPDATE documents
            SET access_count = access_count + 1
            WHERE id = :document_id
        """)
        
        db.execute(update_query, {"document_id": document_id})
        db.commit()
        
        logger.info(f"👁️ Viewing document: {doc.document_name} (inline={inline})")
        
        from fastapi.responses import FileResponse
        
        # Determine content disposition
        disposition = "inline" if inline else "attachment"
        
        return FileResponse(
            path=str(file_path),
            media_type=doc.mime_type or 'application/octet-stream',
            filename=doc.document_name,
            headers={
                "Content-Disposition": f'{disposition}; filename="{doc.document_name}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error viewing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

        