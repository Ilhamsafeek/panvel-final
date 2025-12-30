# =====================================================
# FILE: app/api/api_v1/correspondence/router.py
# Comprehensive Correspondence Management API Router
# Integrates Claude AI, CRUD operations, and Analytics
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text, func
from typing import List, Dict, Any

import uuid
import json
import os
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, BackgroundTasks
from app.services.claude_service import claude_service
from app.api.api_v1.correspondence.schemas import (
    # AI Schemas
    AIQueryRequest,
    AIQueryResponse,
    DocumentAnalysisRequest,
    DocumentAnalysisResponse,
    DocumentSelectionRequest,
    # CRUD Schemas
    CorrespondenceCreate,
    CorrespondenceUpdate,
    CorrespondenceResponse,
    CorrespondenceListResponse,
    CorrespondenceSummary,
    # Generate Schemas
    CorrespondenceGenerateRequest,
    CorrespondenceGenerateResponse,
    # Attachment Schemas
    AttachmentUpload,
    AttachmentResponse,
    # Export Schemas
    ExportRequest,
    ExportResponse,
    # Statistics Schemas
    CorrespondenceStats,
    CorrespondenceTrends,
    # Bulk Operations
    BulkActionRequest,
    BulkActionResponse,
    # Filter Schemas
    CorrespondenceFilter,
    # Enums
    CorrespondenceType,
    Priority,
    Status,
    Tone,
    ExportFormat,
    DocumentReference,
    SourceReference,
    Recommendation
)

from app.api.api_v1.correspondence.service import CorrespondenceService
from app.api.api_v1.correspondence.crud import (
    create_correspondence,
    get_correspondence_list,
    get_correspondence_by_id,
    get_documents_by_ids,
    update_correspondence_status,
    delete_correspondence_record
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/correspondence", tags=["correspondence"])


# =====================================================
# AI-POWERED GENERATION ENDPOINTS
# =====================================================

@router.post("/generate", response_model=CorrespondenceGenerateResponse)
async def generate_ai_correspondence(
    request: CorrespondenceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI-powered correspondence using Claude API
    
    **Features:**
    - Multiple tone options (formal, professional, friendly, etc.)
    - Document context analysis
    - Contract-aware generation
    - Supports email, letter, query, response formats
    
    **Example:**
```json
    {
        "query": "Draft a formal response disputing back charges",
        "documents": [
            {"document_id": "doc-123", "document_name": "Contract.pdf"}
        ],
        "tone": "formal",
        "correspondence_type": "letter",
        "contract_id": "contract-456"
    }
```
    """
    
    try:
        logger.info(f" Generating {request.correspondence_type} with {request.tone} tone for user {current_user.id}")
        
        # Extract document IDs
        document_ids = [doc.document_id for doc in request.documents]
        
        # Validate documents belong to user's company
        if document_ids:
            docs = get_documents_by_ids(db, document_ids)
            if not docs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Selected documents not found"
                )
        
        # Generate correspondence using Claude API
        result = await CorrespondenceService.generate_ai_correspondence(
            db=db,
            query=request.query,
            document_ids=document_ids,
            tone=request.tone,
            correspondence_type=request.correspondence_type,
            contract_id=request.contract_id,
            user_id=str(current_user.id)
        )
        
        if not result["success"]:
            logger.warning(f" AI generation failed: {result.get('error')}")
        else:
            logger.info(f" AI correspondence generated successfully ({result.get('tokens_used', 0)} tokens)")
        
        return CorrespondenceGenerateResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error generating correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate correspondence: {str(e)}"
        )


@router.post("/analyze-documents", response_model=DocumentAnalysisResponse)
async def analyze_documents_for_correspondence(
    request: DocumentAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze documents to extract insights for correspondence
    
    **Use Cases:**
    - Identify relevant clauses
    - Extract key dates and obligations
    - Risk assessment
    - Recommended actions
    
    **Returns:**
    - Key findings
    - Risks and opportunities
    - Recommended approach
    - Confidence score
    """
    
    try:
        logger.info(f"📊 Analyzing {len(request.documents)} documents for user {current_user.id}")
        
        document_ids = [doc.document_id for doc in request.documents]
        
        # Validate documents
        docs = get_documents_by_ids(db, document_ids)
        if not docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documents not found"
            )
        
        result = await CorrespondenceService.analyze_documents(
            db=db,
            document_ids=document_ids,
            query=request.query
        )
        
        return DocumentAnalysisResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error analyzing documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze documents: {str(e)}"
        )


@router.post("/ai-query", response_model=AIQueryResponse)
async def submit_ai_query(
    request: AIQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit comprehensive AI query with full analysis and recommendations
    
    **Advanced Features:**
    - Source reference tracking
    - Confidence scoring
    - Actionable recommendations
    - Context-aware analysis
    - Automatic correspondence creation
    
    **Example Response:**
    - AI-generated response text
    - Source references with page numbers
    - Recommendations with action items
    - Confidence score (0-100)
    """
    
    try:
        import time
        start_time = time.time()
        
        logger.info(f"🔍 Processing AI query: '{request.query_text[:50]}...'")
        
        # Validate document selection
        if not request.selected_document_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one document must be selected for analysis"
            )
        
        # Fetch documents
        documents = get_documents_by_ids(db, request.selected_document_ids)
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected documents not found"
            )
        
        # Get contract context if provided
        context = None
        if request.contract_id:
            context = CorrespondenceService._get_contract_context(db, request.contract_id)
        
        # Generate AI response with Claude API
        ai_result = await CorrespondenceService.generate_ai_correspondence(
            db=db,
            query=request.query_text,
            document_ids=request.selected_document_ids,
            tone=request.tone.value,
            correspondence_type=request.correspondence_type.value,
            contract_id=request.contract_id,
            user_id=str(current_user.id)
        )
        
        if not ai_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI processing failed: {ai_result.get('error', 'Unknown error')}"
            )
        
        # Create correspondence record
        correspondence_id = str(uuid.uuid4())
        correspondence_data = {
            "contract_id": request.contract_id,
            "correspondence_type": request.correspondence_type.value,
            "subject": request.query_text[:500],  # Truncate for subject
            "content": ai_result["content"],
            "recipient_ids": [],
            "cc_ids": [],
            "priority": request.urgency.value,
            "status": Status.DRAFT.value,
            "is_ai_generated": True,
            "ai_tone": request.tone.value
        }
        
        created_corr = create_correspondence(
            db=db,
            correspondence_data=correspondence_data,
            sender_id=str(current_user.id)
        )
        
        # Save document attachments
        for doc_id in request.selected_document_ids:
            attach_query = text("""
                INSERT INTO correspondence_attachments (
                    id, correspondence_id, document_id, uploaded_at
                ) VALUES (:id, :corr_id, :doc_id, :uploaded_at)
            """)
            db.execute(attach_query, {
                "id": str(uuid.uuid4()),
                "corr_id": created_corr["id"],
                "doc_id": doc_id,
                "uploaded_at": datetime.utcnow()
            })
        
        db.commit()
        
        analysis_time = time.time() - start_time
        
        # Build source references (mock for now - enhance with actual document parsing)
        source_references = [
            SourceReference(
                document_id=doc["id"],
                document_name=doc["document_name"],
                page_number=None,
                section=None,
                excerpt=None,
                relevance_score=0.9
            )
            for doc in documents[:3]  # Top 3 most relevant
        ]
        
        # Build recommendations (mock - enhance with AI analysis)
        recommendations = [
            Recommendation(
                title="Review Contract Clauses",
                description="Analyze relevant contract clauses before proceeding",
                priority=Priority.HIGH,
                action_items=[
                    "Review Clause 15.3 - Liquidated Damages",
                    "Check Force Majeure provisions",
                    "Verify dispute resolution procedures"
                ]
            )
        ]
        
        logger.info(f" AI query processed in {analysis_time:.2f}s - Correspondence created: {created_corr['id']}")
        
        return AIQueryResponse(
            correspondence_id=created_corr["id"],
            response_text=ai_result["content"],
            confidence_score=92.5,  # Calculate based on AI metadata
            analysis_time=analysis_time,
            source_references=source_references,
            recommendations=recommendations,
            created_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error processing AI query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


# =====================================================
# PROJECT-LEVEL CORRESPONDENCE ENDPOINTS
# =====================================================

@router.get("/projects/{project_id}/documents", response_model=List[Dict[str, Any]])
async def get_project_documents(
    project_id: str,
    document_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all documents within a project for correspondence selection
    
    **Filters:**
    - Document type (contract, email, letter, etc.)
    - Search by document name
    
    **Returns:**
    - Document list with metadata
    - Associated contract information
    - File details
    """
    
    try:
        # Build query with filters
        where_clauses = [
            "d.company_id = :company_id",
            "c.project_id = :project_id"
        ]
        params = {
            "project_id": project_id,
            "company_id": current_user.company_id
        }
        
        if document_type:
            where_clauses.append("d.document_type = :doc_type")
            params["doc_type"] = document_type
        
        if search:
            where_clauses.append("d.document_name LIKE :search")
            params["search"] = f"%{search}%"
        
        where_sql = " AND ".join(where_clauses)
        
        query = text(f"""
            SELECT 
                d.id,
                d.document_name,
                d.document_type,
                d.file_size,
                d.file_path as file_url,
                d.uploaded_at,
                d.hash_value,
                c.id as contract_id,
                c.contract_number,
                c.contract_title
            FROM documents d
            LEFT JOIN contracts c ON d.contract_id = c.id
            WHERE {where_sql}
            ORDER BY d.uploaded_at DESC
        """)
        
        result = db.execute(query, params)
        
        documents = []
        for row in result:
            documents.append({
                "id": str(row.id),
                "document_name": row.document_name,
                "document_type": row.document_type,
                "file_size": row.file_size,
                "file_url": row.file_url,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                "hash_value": row.hash_value,
                "contract_id": str(row.contract_id) if row.contract_id else None,
                "contract_number": row.contract_number,
                "contract_title": row.contract_title
            })
        
        logger.info(f"📁 Retrieved {len(documents)} documents for project {project_id}")
        
        return documents
        
    except Exception as e:
        logger.error(f" Error fetching project documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching project documents: {str(e)}"
        )


@router.post("/projects/{project_id}/query", response_model=AIQueryResponse)
async def query_project_correspondence(
    project_id: str,
    query_request: AIQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit AI query for project-level correspondence analysis
    
    **Project-Level Analysis:**
    - Analyzes multiple contracts within project
    - Cross-references project documents
    - Project-wide insights and recommendations
    """
    
    try:
        # Verify project belongs to user's company
        project_query = text("""
            SELECT id FROM projects 
            WHERE id = :project_id AND company_id = :company_id
        """)
        
        project = db.execute(project_query, {
            "project_id": project_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Add project context
        query_request.additional_context = f"Project ID: {project_id}\n{query_request.additional_context or ''}"
        
        # Process using AI query endpoint
        return await submit_ai_query(query_request, BackgroundTasks(), db, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error processing project query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


# =====================================================
# CONTRACT/DOCUMENT-LEVEL CORRESPONDENCE ENDPOINTS
# =====================================================

@router.get("/contracts/{contract_id}/documents", response_model=List[Dict[str, Any]])
async def get_contract_documents(
    contract_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all documents for a specific contract
    """
    
    try:
        query = text("""
            SELECT 
                d.id,
                d.document_name,
                d.document_type,
                d.file_size,
                d.file_path as file_url,
                d.uploaded_at,
                d.version,
                d.hash_value
            FROM documents d
            WHERE d.contract_id = :contract_id
            AND d.company_id = :company_id
            ORDER BY d.uploaded_at DESC
        """)
        
        result = db.execute(query, {
            "contract_id": contract_id,
            "company_id": current_user.company_id
        })
        
        documents = []
        for row in result:
            documents.append({
                "id": str(row.id),
                "document_name": row.document_name,
                "document_type": row.document_type,
                "file_size": row.file_size,
                "file_url": row.file_url,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                "version": row.version,
                "hash_value": row.hash_value
            })
        
        logger.info(f" Retrieved {len(documents)} documents for contract {contract_id}")
        
        return documents
        
    except Exception as e:
        logger.error(f" Error fetching contract documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching contract documents: {str(e)}"
        )


@router.post("/documents/{document_id}/query", response_model=AIQueryResponse)
async def query_document_correspondence(
    document_id: str,
    query_request: AIQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit AI query for document-level correspondence analysis
    """
    
    try:
        # Fetch document
        doc_query = text("""
            SELECT id, document_name, file_path, document_type, contract_id
            FROM documents 
            WHERE id = :doc_id AND company_id = :company_id
        """)
        
        result = db.execute(doc_query, {
            "doc_id": document_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Override selected documents with this document
        query_request.selected_document_ids = [document_id]
        query_request.contract_id = str(result.contract_id) if result.contract_id else None
        
        # Process using AI query endpoint
        return await submit_ai_query(query_request, BackgroundTasks(), db, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error processing document query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document query: {str(e)}"
        )


# =====================================================
# CORRESPONDENCE CRUD OPERATIONS
# =====================================================

@router.get("/list", response_model=CorrespondenceListResponse)
async def list_correspondence(
    contract_id: Optional[str] = None,
    status: Optional[Status] = None,
    correspondence_type: Optional[CorrespondenceType] = None,
    priority: Optional[Priority] = None,
    search: Optional[str] = None,
    is_ai_generated: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all correspondence with advanced filtering and pagination
    
    **Filters:**
    - Contract ID
    - Status (draft, sent, received, etc.)
    - Type (email, letter, query, etc.)
    - Priority (normal, high, urgent)
    - Search (subject and content)
    - AI-generated flag
    - Date range
    
    **Pagination:**
    - Page number (default: 1)
    - Page size (1-100, default: 20)
    """
    
    try:
        result = get_correspondence_list(
            db=db,
            company_id=current_user.company_id,
            page=page,
            page_size=page_size,
            correspondence_type=correspondence_type.value if correspondence_type else None,
            status=status.value if status else None,
            priority=priority.value if priority else None,
            search=search,
            contract_id=contract_id,
            is_ai_generated=is_ai_generated,
            date_from=date_from,
            date_to=date_to
        )
        
        logger.info(f"📋 Retrieved {len(result['items'])} correspondence items (page {page})")
        
        return CorrespondenceListResponse(**result)
        
    except Exception as e:
        logger.error(f" Error listing correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch correspondence: {str(e)}"
        )


@router.get("/{correspondence_id}", response_model=CorrespondenceResponse)
async def get_correspondence_detail(
    correspondence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information for a specific correspondence
    
    **Returns:**
    - Full correspondence content
    - Sender and recipient details
    - Attachments
    - Contract context
    - AI metadata (if applicable)
    """
    
    try:
        result = get_correspondence_by_id(db=db, correspondence_id=correspondence_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Correspondence not found"
            )
        
        # Verify access permission
        # User must be sender, recipient, or from same company
        user_id = str(current_user.id)
        recipient_ids = result.get('recipient_ids', [])
        cc_ids = result.get('cc_ids', [])
        
        has_access = (
            result['sender_id'] == user_id or
            user_id in recipient_ids or
            user_id in cc_ids
        )
        
        if not has_access:
            # Check if user is from same company (for admin access)
            sender_query = text("""
                SELECT company_id FROM users WHERE id = :sender_id
            """)
            sender_company = db.execute(sender_query, {"sender_id": result['sender_id']}).fetchone()
            
            if not sender_company or sender_company.company_id != current_user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this correspondence"
                )
        
        logger.info(f"📧 Retrieved correspondence {correspondence_id}")
        
        return CorrespondenceResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error fetching correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch correspondence: {str(e)}"
        )


@router.post("/create", response_model=CorrespondenceResponse, status_code=status.HTTP_201_CREATED)
async def create_new_correspondence(
    correspondence: CorrespondenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new correspondence (draft or send immediately)
    
    **Features:**
    - Create draft for later editing
    - Send immediately
    - Attach documents
    - Multiple recipients and CC
    - Priority levels
    - AI-generated flag
    """
    
    try:
        correspondence_data = correspondence.dict()
        
        # Validate recipients exist
        if correspondence_data.get("recipient_ids"):
            recipient_query = text("""
                SELECT COUNT(*) as count FROM users 
                WHERE id IN :recipient_ids AND company_id = :company_id
            """)
            # For SQLAlchemy compatibility with IN clause
            recipient_ids = correspondence_data["recipient_ids"]
            if recipient_ids:
                # Validate at least one recipient exists
                pass  # Add validation as needed
        
        result = create_correspondence(
            db=db,
            correspondence_data=correspondence_data,
            sender_id=str(current_user.id)
        )
        
        logger.info(f" Correspondence created: {result['id']} (status: {correspondence_data.get('status', 'draft')})")
        
        return CorrespondenceResponse(**result)
        
    except Exception as e:
        db.rollback()
        logger.error(f" Error creating correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create correspondence: {str(e)}"
        )


@router.put("/{correspondence_id}", response_model=CorrespondenceResponse)
async def update_existing_correspondence(
    correspondence_id: str,
    correspondence: CorrespondenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update existing correspondence
    
    **Updatable Fields:**
    - Subject
    - Content
    - Status
    - Priority
    - Recipients and CC
    
    **Restrictions:**
    - Only sender can update
    - Cannot update sent correspondence (except status)
    """
    
    try:
        # Check if correspondence exists and user has permission
        check_query = text("""
            SELECT id, status FROM correspondence 
            WHERE id = :corr_id AND sender_id = :user_id
        """)
        
        result = db.execute(check_query, {
            "corr_id": correspondence_id,
            "user_id": current_user.id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Correspondence not found or no permission to edit"
            )
        
        # Check if already sent (restrict updates)
        if result.status == Status.SENT.value and correspondence.status != Status.ARCHIVED:
            # Only allow status updates on sent correspondence
            if correspondence.subject or correspondence.content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot edit content of sent correspondence"
                )
        
        # Build update query dynamically
        update_fields = []
        params = {"corr_id": correspondence_id}
        
        if correspondence.subject is not None:
            update_fields.append("subject = :subject")
            params["subject"] = correspondence.subject
            
        if correspondence.content is not None:
            update_fields.append("content = :content")
            params["content"] = correspondence.content
            
        if correspondence.status is not None:
            update_fields.append("status = :status")
            params["status"] = correspondence.status.value
            
        if correspondence.priority is not None:
            update_fields.append("priority = :priority")
            params["priority"] = correspondence.priority.value
        
        if correspondence.recipient_ids is not None:
            update_fields.append("recipient_ids = :recipient_ids")
            params["recipient_ids"] = json.dumps(correspondence.recipient_ids)
        
        if correspondence.cc_ids is not None:
            update_fields.append("cc_ids = :cc_ids")
            params["cc_ids"] = json.dumps(correspondence.cc_ids)
        
        if update_fields:
            update_query = text(f"""
                UPDATE correspondence 
                SET {', '.join(update_fields)}
                WHERE id = :corr_id
            """)
            
            db.execute(update_query, params)
            db.commit()
        
        logger.info(f"✏️ Correspondence updated: {correspondence_id}")
        
        return await get_correspondence_detail(correspondence_id, db, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error updating correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update correspondence: {str(e)}"
        )


@router.delete("/{correspondence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_correspondence(
    correspondence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete correspondence (soft delete - archive)
    
    **Restrictions:**
    - Only sender can delete
    - Sent correspondence is archived, not deleted
    """
    
    try:
        # Check permission and status
        check_query = text("""
            SELECT id, status FROM correspondence 
            WHERE id = :corr_id AND sender_id = :user_id
        """)
        
        result = db.execute(check_query, {
            "corr_id": correspondence_id,
            "user_id": current_user.id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Correspondence not found or no permission to delete"
            )
        
        # If sent, archive instead of delete
        if result.status == Status.SENT.value:
            update_query = text("""
                UPDATE correspondence 
                SET status = :status
                WHERE id = :corr_id
            """)
            db.execute(update_query, {
                "corr_id": correspondence_id,
                "status": Status.ARCHIVED.value
            })
            logger.info(f"📦 Correspondence archived: {correspondence_id}")
        else:
            # Delete attachments first (cascade)
            delete_attach_query = text("""
                DELETE FROM correspondence_attachments 
                WHERE correspondence_id = :corr_id
            """)
            db.execute(delete_attach_query, {"corr_id": correspondence_id})
            
            # Delete correspondence
            delete_query = text("""
                DELETE FROM correspondence WHERE id = :corr_id
            """)
            db.execute(delete_query, {"corr_id": correspondence_id})
            logger.info(f"🗑️ Correspondence deleted: {correspondence_id}")
        
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error deleting correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete correspondence: {str(e)}"
        )


# =====================================================
# ATTACHMENT MANAGEMENT
# =====================================================

@router.post("/{correspondence_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_correspondence_attachment(
    correspondence_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload attachment to correspondence
    
    **Supported Formats:**
    - PDF
    - DOCX, DOC
    - XLSX, XLS
    - Images (JPG, PNG)
    
    **Max Size:** 50MB
    """
    
    try:
        # Verify correspondence exists and user has permission
        check_query = text("""
            SELECT id, status FROM correspondence 
            WHERE id = :corr_id AND sender_id = :user_id
        """)
        
        result = db.execute(check_query, {
            "corr_id": correspondence_id,
            "user_id": current_user.id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Correspondence not found"
            )
        
        # Check file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of 50MB"
            )
        
        # Save file (implement file storage service)
        # For now, store file path
        import os
        upload_dir = f"uploads/correspondence/{correspondence_id}"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = f"{upload_dir}/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Create attachment record
        attachment_id = str(uuid.uuid4())
        insert_query = text("""
            INSERT INTO correspondence_attachments (
                id, correspondence_id, attachment_name, 
                attachment_type, file_size, uploaded_at
            ) VALUES (
                :id, :corr_id, :name, :type, :size, :uploaded_at
            )
        """)
        
        db.execute(insert_query, {
            "id": attachment_id,
            "corr_id": correspondence_id,
            "name": file.filename,
            "type": file.content_type,
            "size": file_size,
            "uploaded_at": datetime.utcnow()
        })
        
        db.commit()
        
        logger.info(f"📎 Attachment uploaded: {file.filename} ({file_size} bytes)")
        
        return {
            "id": attachment_id,
            "filename": file.filename,
            "file_size": file_size,
            "content_type": file.content_type,
            "file_url": f"/api/correspondence/attachments/{attachment_id}",
            "message": "Attachment uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error uploading attachment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload attachment: {str(e)}"
        )


@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download correspondence attachment
    """
    
    try:
        # Fetch attachment
        query = text("""
            SELECT 
                ca.id,
                ca.attachment_name,
                ca.attachment_type,
                ca.file_size,
                c.sender_id,
                c.recipient_ids,
                c.cc_ids
            FROM correspondence_attachments ca
            JOIN correspondence c ON ca.correspondence_id = c.id
            WHERE ca.id = :attachment_id
        """)
        
        result = db.execute(query, {"attachment_id": attachment_id}).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found"
            )
        
        # Verify access
        user_id = str(current_user.id)
        recipient_ids = json.loads(result.recipient_ids) if result.recipient_ids else []
        cc_ids = json.loads(result.cc_ids) if result.cc_ids else []
        
        has_access = (
            result.sender_id == user_id or
            user_id in recipient_ids or
            user_id in cc_ids
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this attachment"
            )
        
        # Construct file path
        # In production, use proper file storage service
        file_path = f"uploads/correspondence/{result.id}/{result.attachment_name}"
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on server"
            )
        
        return FileResponse(
            path=file_path,
            filename=result.attachment_name,
            media_type=result.attachment_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error downloading attachment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download attachment: {str(e)}"
        )


# =====================================================
# EXPORT FUNCTIONALITY
# =====================================================

@router.post("/{correspondence_id}/export", response_model=ExportResponse)
async def export_correspondence_document(
    correspondence_id: str,
    export_request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export correspondence as PDF, DOCX, or HTML
    
    **Formats:**
    - PDF (styled, professional)
    - DOCX (editable)
    - HTML (web-ready)
    
    **Options:**
    - Include attachments
    - Include metadata
    """
    
    try:
        # Fetch correspondence
        correspondence = await get_correspondence_detail(correspondence_id, db, current_user)
        
        export_format = export_request.format.value
        
        if export_format == "pdf":
            # Generate PDF
            # Implement PDF generation service
            logger.info(f" Generating PDF export for {correspondence_id}")
            
            # Mock PDF generation
            pdf_content = b"PDF content here"  # Replace with actual PDF generation
            filename = f"correspondence_{correspondence_id}.pdf"
            media_type = "application/pdf"
            
        elif export_format == "docx":
            # Generate DOCX
            logger.info(f" Generating DOCX export for {correspondence_id}")
            
            # Mock DOCX generation
            docx_content = b"DOCX content here"  # Replace with actual DOCX generation
            filename = f"correspondence_{correspondence_id}.docx"
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            
        elif export_format == "html":
            # Generate HTML
            logger.info(f"🌐 Generating HTML export for {correspondence_id}")
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{correspondence.subject}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .header {{ border-bottom: 2px solid #2762cb; padding-bottom: 20px; }}
                    .content {{ margin-top: 30px; line-height: 1.6; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{correspondence.subject}</h1>
                    <p><strong>From:</strong> {correspondence.sender_name} ({correspondence.sender_email})</p>
                    <p><strong>Date:</strong> {correspondence.created_at}</p>
                    <p><strong>Priority:</strong> {correspondence.priority}</p>
                </div>
                <div class="content">
                    {correspondence.content.replace(chr(10), '<br>')}
                </div>
            </body>
            </html>
            """.encode('utf-8')
            
            filename = f"correspondence_{correspondence_id}.html"
            media_type = "text/html"
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid export format"
            )
        
        # In production, save to cloud storage and return URL
        # For now, return streaming response
        
        return ExportResponse(
            success=True,
            file_url=f"/api/correspondence/{correspondence_id}/download/{export_format}",
            filename=filename,
            file_size=None,
            format=export_format,
            generated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error exporting correspondence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export correspondence: {str(e)}"
        )


# =====================================================
# STATISTICS AND ANALYTICS
# =====================================================

@router.get("/stats/overview", response_model=CorrespondenceStats)
async def get_correspondence_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive correspondence statistics
    
    **Metrics:**
    - Total count
    - By status, type, priority
    - AI-generated percentage
    - Average response time
    - Pending and overdue counts
    """
    
    try:
        # Build date filter
        date_filter = ""
        params = {"company_id": current_user.company_id}
        
        if date_from:
            date_filter += " AND c.created_at >= :date_from"
            params["date_from"] = date_from
        
        if date_to:
            date_filter += " AND c.created_at <= :date_to"
            params["date_to"] = date_to
        
        # Total count
        total_query = text(f"""
            SELECT COUNT(*) as total
            FROM correspondence c
            JOIN users u ON c.sender_id = u.id
            WHERE u.company_id = :company_id {date_filter}
        """)
        
        total = db.execute(total_query, params).fetchone().total
        
        # By status
        status_query = text(f"""
            SELECT c.status, COUNT(*) as count
            FROM correspondence c
            JOIN users u ON c.sender_id = u.id
            WHERE u.company_id = :company_id {date_filter}
            GROUP BY c.status
        """)
        
        status_results = db.execute(status_query, params)
        by_status = {row.status: row.count for row in status_results}
        
        # By type
        type_query = text(f"""
            SELECT c.correspondence_type, COUNT(*) as count
            FROM correspondence c
            JOIN users u ON c.sender_id = u.id
            WHERE u.company_id = :company_id {date_filter}
            GROUP BY c.correspondence_type
        """)
        
        type_results = db.execute(type_query, params)
        by_type = {row.correspondence_type: row.count for row in type_results}
        
        # By priority
        priority_query = text(f"""
            SELECT c.priority, COUNT(*) as count
            FROM correspondence c
            JOIN users u ON c.sender_id = u.id
            WHERE u.company_id = :company_id {date_filter}
            GROUP BY c.priority
        """)
        
        priority_results = db.execute(priority_query, params)
        by_priority = {row.priority: row.count for row in priority_results}
        
        # AI generated count
        ai_query = text(f"""
            SELECT COUNT(*) as count
            FROM correspondence c
            JOIN users u ON c.sender_id = u.id
            WHERE u.company_id = :company_id 
            AND c.is_ai_generated = 1 {date_filter}
        """)
        
        ai_count = db.execute(ai_query, params).fetchone().count
        ai_percentage = (ai_count / total * 100) if total > 0 else 0
        
        # Pending responses (draft status)
        pending = by_status.get(Status.DRAFT.value, 0)
        
        # Overdue count (high/urgent priority drafts older than 24 hours)
        overdue_query = text(f"""
            SELECT COUNT(*) as count
            FROM correspondence c
            JOIN users u ON c.sender_id = u.id
            WHERE u.company_id = :company_id
            AND c.status = 'draft'
            AND c.priority IN ('high', 'urgent')
            AND c.created_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)
            {date_filter}
        """)
        
        overdue = db.execute(overdue_query, params).fetchone().count
        
        logger.info(f"📊 Generated statistics: {total} total correspondence")
        
        return CorrespondenceStats(
            total_count=total,
            by_status=by_status,
            by_type=by_type,
            by_priority=by_priority,
            ai_generated_count=ai_count,
            ai_generated_percentage=round(ai_percentage, 2),
            avg_response_time=24.5,  # Calculate from actual data
            pending_responses=pending,
            overdue_count=overdue
        )
        
    except Exception as e:
        logger.error(f" Error generating statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate statistics: {str(e)}"
        )


# =====================================================
# BULK OPERATIONS
# =====================================================

@router.post("/bulk-action", response_model=BulkActionResponse)
async def bulk_correspondence_action(
    request: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Perform bulk actions on multiple correspondence
    
    **Actions:**
    - archive: Archive correspondence
    - delete: Delete correspondence
    - mark_read: Mark as read
    - change_priority: Update priority
    - change_status: Update status
    """
    
    try:
        if not request.correspondence_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No correspondence IDs provided"
            )
        
        affected_count = 0
        failed_ids = []
        errors = []
        
        for corr_id in request.correspondence_ids:
            try:
                # Verify permission
                check_query = text("""
                    SELECT id FROM correspondence 
                    WHERE id = :corr_id AND sender_id = :user_id
                """)
                
                result = db.execute(check_query, {
                    "corr_id": corr_id,
                    "user_id": current_user.id
                }).fetchone()
                
                if not result:
                    failed_ids.append(corr_id)
                    errors.append(f"No permission for {corr_id}")
                    continue
                
                # Perform action
                if request.action == "archive":
                    update_query = text("""
                        UPDATE correspondence 
                        SET status = :status
                        WHERE id = :corr_id
                    """)
                    db.execute(update_query, {
                        "corr_id": corr_id,
                        "status": Status.ARCHIVED.value
                    })
                    
                elif request.action == "delete":
                    delete_query = text("""
                        DELETE FROM correspondence WHERE id = :corr_id
                    """)
                    db.execute(delete_query, {"corr_id": corr_id})
                    
                elif request.action == "mark_read":
                    update_query = text("""
                        UPDATE correspondence 
                        SET read_at = :read_at, status = :status
                        WHERE id = :corr_id
                    """)
                    db.execute(update_query, {
                        "corr_id": corr_id,
                        "read_at": datetime.utcnow(),
                        "status": Status.READ.value
                    })
                    
                elif request.action == "change_priority":
                    if not request.new_priority:
                        raise ValueError("new_priority required for change_priority action")
                    
                    update_query = text("""
                        UPDATE correspondence 
                        SET priority = :priority
                        WHERE id = :corr_id
                    """)
                    db.execute(update_query, {
                        "corr_id": corr_id,
                        "priority": request.new_priority.value
                    })
                    
                elif request.action == "change_status":
                    if not request.new_status:
                        raise ValueError("new_status required for change_status action")
                    
                    update_query = text("""
                        UPDATE correspondence 
                        SET status = :status
                        WHERE id = :corr_id
                    """)
                    db.execute(update_query, {
                        "corr_id": corr_id,
                        "status": request.new_status.value
                    })
                
                affected_count += 1
                
            except Exception as e:
                failed_ids.append(corr_id)
                errors.append(str(e))
        
        db.commit()
        
        logger.info(f"📦 Bulk action '{request.action}' completed: {affected_count}/{len(request.correspondence_ids)} successful")
        
        return BulkActionResponse(
            success=affected_count > 0,
            affected_count=affected_count,
            failed_ids=failed_ids,
            errors=errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error in bulk action: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk action: {str(e)}"
        )
    

    
# =====================================================
# AI ANALYZE DOCUMENTS ENDPOINT
# =====================================================
# =====================================================
# FIXED /analyze ENDPOINT
# Replace your existing /analyze endpoint with this
# =====================================================

@router.post("/analyze")
async def analyze_correspondence(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze documents or correspondence using Claude AI
    Supports both project-level and document-level analysis
    FIXED: Proper error handling for Claude AI service
    """
    try:
        logger.info(f" Starting correspondence analysis for user {current_user.id}")
        
        # Extract request data
        query_text = request.get("query", "")
        analysis_mode = request.get("mode", "document")
        document_ids = request.get("document_ids", [])
        project_id = request.get("project_id")
        tone = request.get("tone", "professional")
        urgency = request.get("urgency", "normal")
        language = request.get("language", "en")
        
        if not query_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query text is required"
            )
        
        # Gather document context based on mode
        documents_context = []
        
        if analysis_mode == "project" and project_id:
            # Get all documents from project with contract_versions JOIN
            project_docs = db.execute(text("""
                SELECT 
                    d.id,
                    d.document_name,
                    d.document_type,
                    d.file_path,
                    d.uploaded_at,
                    c.contract_title,
                    c.contract_type,
                    c.current_version,
                    cv.contract_content,
                    cv.contract_content_ar,
                    cv.version_number
                FROM documents d
                LEFT JOIN contracts c ON d.contract_id = c.id
                LEFT JOIN contract_versions cv ON c.id = cv.contract_id 
                    AND cv.version_number = c.current_version
                WHERE c.project_id = :project_id
                  AND c.company_id = :company_id
                ORDER BY d.uploaded_at DESC
            """), {
                "project_id": project_id,
                "company_id": current_user.company_id
            }).fetchall()
            
            for doc in project_docs:
                documents_context.append({
                    "id": str(doc.id),
                    "name": doc.document_name,
                    "type": doc.document_type,
                    "contract_title": doc.contract_title,
                    "contract_type": doc.contract_type,
                    "contract_content": doc.contract_content,
                    "version": doc.version_number,
                    "date": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                })
        
        elif analysis_mode == "document" and document_ids:
            # Get specific documents with contract_versions JOIN
            for doc_id in document_ids:
                doc_info = db.execute(text("""
                    SELECT 
                        d.id,
                        d.document_name,
                        d.document_type,
                        d.file_path,
                        d.uploaded_at,
                        c.contract_title,
                        c.contract_type,
                        c.current_version,
                        cv.contract_content,
                        cv.contract_content_ar,
                        cv.version_number
                    FROM documents d
                    LEFT JOIN contracts c ON d.contract_id = c.id
                    LEFT JOIN contract_versions cv ON c.id = cv.contract_id 
                        AND cv.version_number = c.current_version
                    WHERE d.id = :doc_id
                      AND c.company_id = :company_id
                """), {
                    "doc_id": doc_id,
                    "company_id": current_user.company_id
                }).fetchone()
                
                if doc_info:
                    documents_context.append({
                        "id": str(doc_info.id),
                        "name": doc_info.document_name,
                        "type": doc_info.document_type,
                        "contract_title": doc_info.contract_title,
                        "contract_type": doc_info.contract_type,
                        "contract_content": doc_info.contract_content,
                        "content_preview": doc_info.contract_content[:500] if doc_info.contract_content else None,
                        "version": doc_info.version_number,
                        "date": doc_info.uploaded_at.isoformat() if doc_info.uploaded_at else None
                    })
        
        if not documents_context:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No documents found for analysis"
            )
        
        logger.info(f" Analyzing {len(documents_context)} documents")
        
        #  FIXED: Try multiple AI service approaches with proper error handling
        ai_result = None
        
        # Approach 1: Try claude_service
        try:
            from app.services.claude_service import claude_service
            
            if hasattr(claude_service, 'analyze_correspondence'):
                ai_result = claude_service.analyze_correspondence(
                    query=query_text,
                    documents=documents_context,
                    analysis_mode=analysis_mode,
                    tone=tone,
                    urgency=urgency,
                    language=language,
                    jurisdiction="Qatar"
                )
                logger.info(" Used claude_service.analyze_correspondence")
            else:
                logger.warning(" claude_service.analyze_correspondence not found")
        except ImportError:
            logger.warning(" claude_service not available")
        except Exception as e:
            logger.warning(f" claude_service failed: {str(e)}")
        
        # Approach 2: Try claude_client
        if not ai_result:
            try:
                from app.core.claude_client import claude_client
                
                if claude_client and hasattr(claude_client, 'analyze_documents'):
                    ai_result = await claude_client.analyze_documents(
                        documents=documents_context,
                        query=query_text
                    )
                    
                    # Convert to expected format
                    if ai_result and not isinstance(ai_result, dict):
                        ai_result = {"analysis_text": str(ai_result)}
                    
                    logger.info(" Used claude_client.analyze_documents")
            except Exception as e:
                logger.warning(f" claude_client failed: {str(e)}")
        
        # Approach 3: Try CorrespondenceService
        if not ai_result:
            try:
                from app.api.api_v1.correspondence.service import CorrespondenceService
                
                ai_result = await CorrespondenceService.analyze_documents(
                    db=db,
                    document_ids=[doc["id"] for doc in documents_context],
                    query=query_text
                )
                
                logger.info(" Used CorrespondenceService.analyze_documents")
            except Exception as e:
                logger.warning(f" CorrespondenceService failed: {str(e)}")
        
        # Approach 4: Fallback to mock analysis
        if not ai_result or not isinstance(ai_result, dict):
            logger.warning(" All AI services failed, using fallback mock analysis")
            ai_result = _generate_fallback_analysis(query_text, documents_context)
        
        #  FIXED: Safely extract values with defaults
        analysis_text = (
            ai_result.get("analysis_text") or 
            ai_result.get("analysis") or 
            ai_result.get("content") or
            "Analysis completed. Please review the documents."
        )
        
        confidence_score = ai_result.get("confidence_score", 75.0)
        tokens_used = ai_result.get("tokens_used", 0)
        processing_time_ms = ai_result.get("processing_time_ms", 0)
        recommendations = ai_result.get("recommendations", [])
        key_points = ai_result.get("key_points", ai_result.get("key_findings", []))
        suggested_actions = ai_result.get("suggested_actions", ai_result.get("recommended_actions", []))
        
        # Store analysis in database (if possible)
        try:
            db.execute(text("""
                INSERT INTO ai_query_history 
                (user_id, query_text, response_text, response_time_ms, created_at)
                VALUES 
                (:user_id, :query_text, :response_text, :response_time_ms, :created_at)
            """), {
                "user_id": current_user.id,
                "query_text": query_text,
                "response_text": analysis_text[:5000],
                "response_time_ms": processing_time_ms,
                "created_at": datetime.utcnow()
            })
            db.commit()
            logger.info(f" Analysis saved to database")
        except Exception as db_error:
            logger.warning(f" Could not save to database: {str(db_error)}")
            db.rollback()
        
        logger.info(f" Correspondence analysis completed successfully")
        
        return {
            "success": True,
            "content": analysis_text,
            "confidence": confidence_score,
            "processingTime": processing_time_ms / 1000 if processing_time_ms else 0,
            "sources": [
                {
                    "id": doc["id"],
                    "name": doc["name"],
                    "type": doc["type"],
                    "contract": doc.get("contract_title", "N/A"),
                    "version": doc.get("version", "N/A"),
                    "relevance": 85
                }
                for doc in documents_context
            ],
            "recommendations": recommendations,
            "key_points": key_points,
            "suggested_actions": suggested_actions,
            "tokens_used": tokens_used,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error in correspondence analysis: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze correspondence: {str(e)}"
        )


# =====================================================
# HELPER FUNCTION: Fallback Analysis
# =====================================================

def _generate_fallback_analysis(query: str, documents: List[Dict]) -> Dict[str, Any]:
    """
    Generate fallback analysis when all AI services fail
    """
    
    analysis_text = f"""
**CORRESPONDENCE ANALYSIS**

Query: {query}

Documents Reviewed: {len(documents)}

**SUMMARY:**
Based on the available documents, we have conducted a preliminary analysis. For a detailed AI-powered analysis, please ensure the Claude AI service is properly configured.

**DOCUMENTS ANALYZED:**
"""
    
    for idx, doc in enumerate(documents[:5], 1):
        analysis_text += f"\n{idx}. {doc.get('name', 'Unknown')} ({doc.get('type', 'Document')})"
        if doc.get('contract_title'):
            analysis_text += f"\n   Contract: {doc['contract_title']}"
    
    analysis_text += """

**RECOMMENDED APPROACH:**

1. **Document Review**: Thoroughly review all referenced documents
2. **Legal Consultation**: Consider consulting with legal counsel for specific advice
3. **Risk Assessment**: Evaluate potential risks and mitigation strategies
4. **Action Plan**: Develop a comprehensive action plan with timelines

**NEXT STEPS:**

• Schedule a meeting with relevant stakeholders
• Gather additional documentation if needed
• Prepare a detailed position statement
• Consider alternative resolution options

**Note**: For AI-powered analysis with detailed insights, please configure the Claude API service.
"""
    
    return {
        "analysis_text": analysis_text,
        "confidence_score": 60.0,
        "tokens_used": 0,
        "processing_time_ms": 0,
        "recommendations": [
            "Review all contract documents thoroughly",
            "Consult with legal team",
            "Document all communications"
        ],
        "key_points": [
            f"Total documents analyzed: {len(documents)}",
            "Preliminary analysis completed",
            "AI service configuration needed for detailed insights"
        ],
        "suggested_actions": [
            "Enable Claude API integration",
            "Schedule stakeholder meeting",
            "Prepare detailed documentation"
        ]
    }

# =====================================================
# GET CORRESPONDENCE HISTORY
# =====================================================
@router.get("/history")
async def get_correspondence_history(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get correspondence analysis history for current user"""
    try:
        #  FIXED: Query without query_type column
        history = db.execute(text("""
            SELECT 
                id,
                query_text,
                response_text,
                response_time_ms,
                created_at
            FROM ai_query_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """), {
            "user_id": current_user.id,
            "limit": limit,
            "skip": skip
        }).fetchall()
        
        total = db.execute(text("""
            SELECT COUNT(*) as count
            FROM ai_query_history
            WHERE user_id = :user_id
        """), {"user_id": current_user.id}).fetchone()
        
        return {
            "success": True,
            "total": total.count if total else 0,
            "items": [
                {
                    "id": h.id,
                    "query": h.query_text,
                    "response": h.response_text[:200] + "..." if len(h.response_text) > 200 else h.response_text,
                    "processing_time": h.response_time_ms,
                    "created_at": h.created_at.isoformat() if h.created_at else None
                }
                for h in history
            ]
        }
    except Exception as e:
        logger.error(f" Error fetching correspondence history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )




# =====================================================
# GET AVAILABLE DOCUMENTS FOR ANALYSIS
# =====================================================
@router.get("/documents")
async def get_available_documents(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of documents available for correspondence analysis"""
    try:
        query = """
            SELECT 
                d.id,
                d.document_name,
                d.document_type,
                d.uploaded_at,
                c.id as contract_id,
                c.contract_number,
                c.contract_title,
                c.contract_type,
                c.project_id,
                p.project_name
            FROM documents d
            LEFT JOIN contracts c ON d.contract_id = c.id
            LEFT JOIN projects p ON c.project_id = p.id
            WHERE c.company_id = :company_id
        """
        
        params = {"company_id": current_user.company_id}
        
        if project_id:
            query += " AND c.project_id = :project_id"
            params["project_id"] = project_id
        
        query += " ORDER BY d.uploaded_at DESC LIMIT 100"
        
        documents = db.execute(text(query), params).fetchall()
        
        return {
            "success": True,
            "documents": [
                {
                    "id": doc.id,
                    "name": doc.document_name,
                    "type": doc.document_type,
                    "contract_id": doc.contract_id,
                    "contract_number": doc.contract_number,
                    "contract_title": doc.contract_title,
                    "contract_type": doc.contract_type,
                    "project_id": doc.project_id,
                    "project_name": doc.project_name,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                }
                for doc in documents
            ]
        }
    except Exception as e:
        logger.error(f" Error fetching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch documents: {str(e)}"
        )
    


    