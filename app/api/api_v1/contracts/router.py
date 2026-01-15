# =====================================================
# FILE: app/api/api_v1/contracts/router.py
# Contract Drafting API Endpoints - COMPLETE VERSION
# All endpoints preserved + better error handling
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
from pathlib import Path as FilePath
import logging
from app.core.config import settings
from uuid import uuid4
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.utils.document_parser import DocumentParser

from app.api.api_v1.contracts.schemas import (
    ContractCreateRequest, ContractUpdateRequest, ContractResponse,
    ContractListResponse, ClauseCreateRequest, ClauseUpdateRequest,
    ClauseResponse, ClauseListResponse, TemplateResponse,
    AIDraftingRequest, AIDraftingResponse
)
from app.api.api_v1.contracts.service import ContractService
from app.models.contract import ContractTemplate,Contract, ContractVersion

from app.services.blockchain_service import blockchain_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contracts", tags=["Contract Drafting"])



# Add this schema with your other schemas
class CommentCreateRequest(BaseModel):
    contract_id: int
    comment_text: str
    selected_text: Optional[str] = None

class CommentResponse(BaseModel):
    success: bool
    message: str
    comment_id: int
    comment: dict



@router.post("/comments/add", response_model=CommentResponse)
async def add_comment_to_contract(
    request: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a comment to a contract - Full permissions by default"""
    try:
        logger.info(f" Adding comment to contract {request.contract_id} by user {current_user.id}")
        
        # Verify contract exists
        contract = db.query(Contract).filter(
            Contract.id == request.contract_id
        ).first()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Insert comment
        query = text("""
            INSERT INTO contract_comments 
            (contract_id, user_id, comment_text, selected_text, created_at)
            VALUES 
            (:contract_id, :user_id, :comment_text, :selected_text, NOW())
        """)
        
        result = db.execute(query, {
            'contract_id': request.contract_id,
            'user_id': current_user.id,
            'comment_text': request.comment_text,
            'selected_text': request.selected_text
        })
        
        db.commit()
        
        comment_id = result.lastrowid
        
        logger.info(f" Comment {comment_id} added successfully")
        
        # =====================================================
        # SEND EMAIL NOTIFICATION TO CONTRACT INITIATOR
        # =====================================================
        try:
            from app.core.email import send_email_smtp
            
            # Check if current user is NOT the contract creator (i.e., is counterparty)
            is_counterparty = (current_user.id != contract.created_by)
            
            if is_counterparty and contract.created_by:
                # Get contract creator details
                creator_query = text("""
                    SELECT 
                        id,
                        CONCAT(first_name, ' ', last_name) as full_name,
                        email
                    FROM users
                    WHERE id = :creator_id
                    AND is_active = 1
                    AND email IS NOT NULL
                """)
                creator = db.execute(creator_query, {
                    "creator_id": contract.created_by
                }).fetchone()
                
                if creator and creator.email:
                    # Get commenter name
                    commenter_name = f"{current_user.first_name} {current_user.last_name}"
                    
                    # Contract URL
                    contract_url = f"https://calim360.com/contract/edit/{request.contract_id}?action=view"
                    
                    # Truncate comment for email preview (first 200 chars)
                    comment_preview = request.comment_text[:200]
                    if len(request.comment_text) > 200:
                        comment_preview += "..."
                    
                    # Truncate selected text for context (first 100 chars)
                    selected_preview = ""
                    if request.selected_text:
                        selected_preview = request.selected_text[:100]
                        if len(request.selected_text) > 100:
                            selected_preview += "..."
                    
                    email_subject = f"New Comment on Contract {contract.contract_number} - Action Required"
                    
                    email_body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                            <div style="background: linear-gradient(135deg, #ff9800 0%, #ff5722 100%); padding: 20px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px;">
                                <h2 style="color: white; margin: 0;"> New Comment on Contract</h2>
                            </div>
                            
                            <p>Hi <strong>{creator.full_name}</strong>,</p>
                            
                            <p><strong>{commenter_name}</strong> has added a comment to your contract and requires your attention.</p>
                            
                            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                                <h3 style="margin-top: 0; color: #2762cb;">Contract Details:</h3>
                                <p style="margin: 5px 0;"><strong>Contract Number:</strong> {contract.contract_number}</p>
                                <p style="margin: 5px 0;"><strong>Contract Title:</strong> {contract.contract_title}</p>
                            </div>
                    """
                    
                    # Add selected text context if available
                    if selected_preview:
                        email_body += f"""
                            <div style="background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; margin: 20px 0; border-radius: 6px;">
                                <p style="margin: 0; color: #1976d2;"><strong>📝 Commented on:</strong></p>
                                <p style="margin: 10px 0 0 0; font-style: italic; color: #424242;">"{selected_preview}"</p>
                            </div>
                        """
                    
                    email_body += f"""
                            <div style="background-color: #fff3cd; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0; border-radius: 6px;">
                                <p style="margin: 0; color: #856404;"><strong> Comment:</strong></p>
                                <p style="margin: 10px 0 0 0;">{comment_preview}</p>
                            </div>
                            
                            <p>Please review and respond to this comment to keep the contract review process moving forward.</p>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{contract_url}" 
                                   style="background: linear-gradient(135deg, #ff9800 0%, #ff5722 100%); 
                                          color: white; 
                                          padding: 12px 30px; 
                                          text-decoration: none; 
                                          border-radius: 6px; 
                                          font-weight: bold;
                                          display: inline-block;">
                                    View Comment & Respond
                                </a>
                            </div>
                            
                            <p style="color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                                This is an automated notification from CALIM 360 - Smart Contract Lifecycle Management System.<br>
                                Please do not reply to this email.
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    # Send email
                    try:
                        send_email_smtp(
                            to_email=creator.email,
                            subject=email_subject,
                            html_body=email_body
                        )
                        logger.info(f"✉️ Comment notification email sent to contract creator {creator.email}")
                    except Exception as email_error:
                        logger.error(f"❌ Failed to send email to creator: {str(email_error)}")
                        # Don't fail the comment if email fails
                else:
                    logger.warning(f"⚠️ Contract creator {contract.created_by} not found or has no email")
            else:
                logger.info("ℹ️ Comment from contract creator, no notification sent")
                
        except Exception as email_exception:
            logger.error(f"❌ Error in email notification process: {str(email_exception)}")
            # Don't fail the comment if email service fails
            pass
        
        return {
            "success": True,
            "message": "Comment added successfully",
            "comment_id": comment_id,
            "comment": {
                "id": comment_id,
                "user_name": f"{current_user.first_name} {current_user.last_name}",
                "comment_text": request.comment_text,
                "selected_text": request.selected_text,
                "created_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error adding comment: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add comment: {str(e)}"
        )



# =====================================================
# Get Comments - Using contract_comments table
# =====================================================
@router.get("/comments/{contract_id}")
async def get_contract_comments(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all comments for a contract - Full access by default"""
    try:
        logger.info(f"📖 Getting comments for contract {contract_id}")
        
        #  SIMPLIFIED: Just verify contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        #  NO PERMISSION CHECKS - All authenticated users can view comments
        
        #  Get comments
        query = text("""
            SELECT 
                cc.id,
                cc.comment_text,
                cc.selected_text,
                cc.created_at,
                u.first_name,
                u.last_name,
                u.profile_picture_url
            FROM contract_comments cc
            INNER JOIN users u ON u.id = cc.user_id
            WHERE cc.contract_id = :contract_id
            ORDER BY cc.created_at DESC
        """)
        
        result = db.execute(query, {'contract_id': contract_id})
        rows = result.fetchall()
        
        comments = []
        for row in rows:
            comments.append({
                'id': row.id,
                'comment_text': row.comment_text,
                'selected_text': row.selected_text or "",
                'author': f"{row.first_name} {row.last_name}",
                'author_picture': row.profile_picture_url,
                'created_at': row.created_at.isoformat() if row.created_at else None
            })
        
        logger.info(f" Found {len(comments)} comments")
        
        return {
            'success': True,
            'comments': comments,
            'total': len(comments)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting comments: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))



# =====================================================
# DELETE Comment (Optional - for future enhancement)
# =====================================================
@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a comment (only by author or admin)"""
    try:
        # Check if comment exists and user owns it
        query = text("""
            SELECT cc.id, cc.user_id, cc.contract_id
            FROM contract_comments cc
            WHERE cc.id = :comment_id
        """)
        
        result = db.execute(query, {'comment_id': comment_id})
        comment = result.fetchone()
        
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        # Only comment author or admin can delete
        # For now, simplified: only author can delete
        if comment.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only delete your own comments")
        
        # Delete comment
        delete_query = text("DELETE FROM contract_comments WHERE id = :comment_id")
        db.execute(delete_query, {'comment_id': comment_id})
        db.commit()
        
        logger.info(f" Comment {comment_id} deleted successfully")
        
        return {
            'success': True,
            'message': 'Comment deleted successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error deleting comment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
          
# =====================================================
# Contract Creation & Basic Operations
# =====================================================

@router.post("/", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    request: ContractCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new contract
    - Creates contract from scratch or from template
    - Auto-generates contract number
    - Logs audit trail
    - Stores hash on blockchain for immutability
    """
    try:
        # Create the contract
        contract = ContractService.create_contract(
            db=db,
            request=request,
            user_id=current_user.id,
            company_id=current_user.company_id
        )
        
        # Generate document content for blockchain hashing
        document_content = f"{contract.contract_number}|{contract.contract_title}|{contract.contract_type}|{contract.start_date}|{contract.end_date}|{contract.contract_value}"
        
        # Store hash on blockchain (async operation)
        try:
            from app.services.blockchain_service import blockchain_service
            from app.models.blockchain import BlockchainRecord, DocumentIntegrity
            
            blockchain_result = await blockchain_service.store_contract_hash(
                contract_id=contract.id,
                document_content=document_content,
                uploaded_by=current_user.id,
                company_id=current_user.company_id,
                contract_number=contract.contract_number,
                contract_type=contract.contract_type
            )
            
            if blockchain_result.get("success"):
                # Store blockchain record in database
                blockchain_record = BlockchainRecord(
                    id=str(uuid.uuid4()),
                    entity_type="contract",
                    entity_id=str(contract.id),
                    transaction_hash=blockchain_result["transaction_id"],
                    block_number=blockchain_result["block_number"],
                    blockchain_network="hyperledger-fabric",
                    status="confirmed",
                    created_at=datetime.utcnow()
                )
                db.add(blockchain_record)
                
                # Store document integrity record
                integrity_record = DocumentIntegrity(
                    id=str(uuid.uuid4()),
                    document_id=str(contract.id),
                    hash_algorithm="SHA-256",
                    document_hash=blockchain_result["document_hash"],
                    blockchain_hash=blockchain_result["transaction_id"],
                    verification_status="verified",
                    last_verified_at=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
                db.add(integrity_record)
                
                db.commit()
                
                logger.info(f" Contract {contract.id} hash stored on blockchain: {blockchain_result['transaction_id']}")
            else:
                logger.warning(f" Blockchain storage failed for contract {contract.id} (non-critical): {blockchain_result.get('error')}")
                
        except Exception as blockchain_error:
            logger.warning(f" Blockchain storage failed (non-critical): {str(blockchain_error)}")
            # Don't fail contract creation if blockchain fails
        
        return ContractResponse.from_orm(contract)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f" Contract creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contract: {str(e)}"
        )


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get contract by ID"""
    contract = ContractService.get_contract_by_id(
        db=db,
        contract_id=contract_id,
        company_id=current_user.company_id
    )
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found"
        )
    
    return ContractResponse.from_orm(contract)


@router.get("/", response_model=ContractListResponse)
async def list_contracts(
    status_filter: Optional[str] = Query(None, alias="status"),
    profile_type: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List contracts with filters
    
    - Filter by status, profile type, project
    - Pagination support
    - Returns total count
    """
    skip = (page - 1) * page_size
    
    contracts, total = ContractService.list_contracts(
        db=db,
        company_id=current_user.company_id,
        status=status_filter,
        profile_type=profile_type,
        project_id=project_id,
        skip=skip,
        limit=page_size
    )
    
    return ContractListResponse(
        total=total,
        items=[ContractResponse.from_orm(c) for c in contracts],
        page=page,
        page_size=page_size
    )

@router.put("/{contract_id}/content", response_model=dict)
def update_contract_content(
    contract_id: int,
    content_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update contract content and create new version"""
    
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Get latest version number
    latest_version = db.query(ContractVersion).filter(
        ContractVersion.contract_id == contract_id
    ).order_by(ContractVersion.version_number.desc()).first()
    
    new_version_number = (latest_version.version_number + 1) if latest_version else 1
    
    # Create new version
    new_version = ContractVersion(
        contract_id=contract_id,
        version_number=new_version_number,
        version_type=content_data.get("version_type", "draft"),
        contract_content=content_data.get("contract_content"),
        contract_content_ar=content_data.get("contract_content_ar"),
        change_summary=content_data.get("change_summary", f"Version {new_version_number} update"),
        is_major_version=content_data.get("is_major_version", False),
        created_by=current_user.id
    )
    
    db.add(new_version)
    
    # Update contract version number
    contract.current_version = new_version_number
    
    db.commit()
    db.refresh(new_version)
    
    return {
        "message": "Contract content updated successfully",
        "version_number": new_version_number,
        "contract_id": contract_id
    }

    
@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft delete a contract"""
    ContractService.delete_contract(
        db=db,
        contract_id=contract_id,
        user_id=current_user.id,
        company_id=current_user.company_id
    )
    return None


# =====================================================
# Contract Content & Versioning
# =====================================================

@router.post("/{contract_id}/content")
async def save_contract_content(
    contract_id: int,
    content: str,
    version_type: str = "draft",
    change_summary: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save the full contract content as a new version"""
    try:
        version = ContractService.save_contract_version(
            db=db,
            contract_id=contract_id,
            contract_content=content,
            user_id=current_user.id,
            version_type=version_type,
            change_summary=change_summary
        )
        return {
            "message": "Contract content saved",
            "version_number": version.version_number,
            "version_id": version.id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )



@router.get("/{contract_id}/content", response_model=dict)
def get_contract_content(
    contract_id: int,
    version_number: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get contract content for specific version"""
    
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Get specific version or latest
    query = db.query(ContractVersion).filter(ContractVersion.contract_id == contract_id)
    
    if version_number:
        query = query.filter(ContractVersion.version_number == version_number)
    else:
        query = query.order_by(ContractVersion.version_number.desc())
    
    version = query.first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Contract version not found")
    
    return {
        "contract_id": contract.id,
        "contract_number": contract.contract_number,
        "contract_title": contract.contract_title,
        "version_number": version.version_number,
        "version_type": version.version_type,
        "contract_content": version.contract_content,
        "contract_content_ar": version.contract_content_ar,
        "file_url": version.file_url,
        "created_at": version.created_at
    }




@router.get("/{contract_id}/versions")
async def get_contract_versions(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all versions of a contract"""
    versions = db.query(ContractVersion).filter(
        ContractVersion.contract_id == contract_id
    ).order_by(desc(ContractVersion.version_number)).all()
    
    return {
        "total": len(versions),
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "version_type": v.version_type,
                "change_summary": v.change_summary,
                "created_by": v.created_by,
                "created_at": v.created_at
            }
            for v in versions
        ]
    }


# =====================================================
# Contract Locking
# =====================================================

@router.post("/{contract_id}/lock", response_model=ContractResponse)
async def lock_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lock contract for editing"""
    contract = ContractService.lock_contract(
        db=db,
        contract_id=contract_id,
        user_id=current_user.id,
        company_id=current_user.company_id
    )
    return ContractResponse.from_orm(contract)


@router.post("/{contract_id}/unlock", response_model=ContractResponse)
async def unlock_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unlock contract"""
    contract = ContractService.unlock_contract(
        db=db,
        contract_id=contract_id,
        user_id=current_user.id,
        company_id=current_user.company_id
    )
    return ContractResponse.from_orm(contract)


# =====================================================
# Clause Management
# =====================================================

@router.post("/clauses", response_model=ClauseResponse, status_code=status.HTTP_201_CREATED)
async def add_clause(
    request: ClauseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a clause to contract"""
    clause = ContractService.add_clause(
        db=db,
        request=request,
        user_id=current_user.id
    )
    return ClauseResponse.from_orm(clause)


@router.get("/{contract_id}/clauses", response_model=ClauseListResponse)
async def get_contract_clauses(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all clauses for a contract"""
    clauses = ContractService.get_contract_clauses(
        db=db,
        contract_id=contract_id
    )
    
    return ClauseListResponse(
        total=len(clauses),
        items=[ClauseResponse.from_orm(c) for c in clauses]
    )


@router.put("/clauses/{clause_id}", response_model=ClauseResponse)
async def update_clause(
    clause_id: int,
    request: ClauseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a clause"""
    clause = ContractService.update_clause(
        db=db,
        clause_id=clause_id,
        request=request,
        user_id=current_user.id
    )
    return ClauseResponse.from_orm(clause)


@router.delete("/clauses/{clause_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clause(
    clause_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a clause"""
    ContractService.delete_clause(
        db=db,
        clause_id=clause_id,
        user_id=current_user.id
    )
    return None


# =====================================================
# AI Drafting
# =====================================================

@router.post("/ai/draft-clause", response_model=AIDraftingResponse)
async def draft_clause_with_ai(
    request: AIDraftingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Use AI to draft a contract clause
    
    - Requires contract_id and clause_title
    - Returns AI-generated clause content
    - Optionally saves to database
    """
    try:
        result = await ContractService.draft_clause_with_ai(
            db=db,
            request=request,
            user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI drafting failed: {str(e)}"
        )


# =====================================================
# Template & Creation Options
# =====================================================

@router.get("/creation-options")
async def get_creation_options(
    profile_type: str = Query(..., description="client, consultant, contractor, sub_contractor"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get available templates and creation options based on profile type
    """
    # Get templates for this profile type
    templates = db.query(ContractTemplate).filter(
        ContractTemplate.is_active == True
    ).all()
    
    # Filter templates by category if needed
    template_list = []
    for template in templates:
        # You can add filtering logic based on profile_type
        template_list.append({
            'id': template.id,
            'name': template.template_name,
            'category': template.template_category,
            'description': template.description,
            'file_url': template.file_url
        })
    
    return {
        'profile_type': profile_type,
        'template_categories': {
            profile_type: template_list
        },
        'creation_methods': ['template', 'upload', 'ai', 'blank'],
        'ai_capabilities': {
            'enabled': True,
            'supports_analysis': True,
            'supports_drafting': True
        }
    }


# =====================================================
# Document Upload
# =====================================================
@router.post("/upload-contract")
async def upload_contract(
    file: UploadFile = File(...),
    contract_title: str = Form(...),
    contract_title_ar: Optional[str] = Form(None),
    contract_type: Optional[str] = Form(None),
    profile_type: str = Form(...),
    contract_value: Optional[float] = Form(None),
    currency: str = Form("QAR"),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload existing contract file and extract actual content"""
    
    try:
        logger.info(f" Upload request from user {current_user.email}")
        logger.info(f"📎 File: {file.filename}, Type: {file.content_type}")
        
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        file_ext = FilePath(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Generate contract number
        year = datetime.now().year
        count = db.query(Contract).filter(
            Contract.contract_number.like(f"CNT-{year}-%"),
            Contract.company_id == current_user.company_id
        ).count()
        contract_number = f"CNT-{year}-{count + 1:04d}"
        
        logger.info(f"🔢 Generated contract number: {contract_number}")
        
        # Parse dates
        parsed_start_date = None
        parsed_end_date = None
        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}")
        
        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}")
        
        # Create contract record
        new_contract = Contract(
            contract_number=contract_number,
            contract_title=contract_title,
            contract_title_ar=contract_title_ar,
            contract_type=contract_type or "general",
            profile_type=profile_type,
            contract_value=contract_value,
            currency=currency,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            project_id=project_id,
            status="draft",
            current_version=1,
            created_by=current_user.id,
            company_id=current_user.company_id
        )
        
        db.add(new_contract)
        db.flush()
        
        logger.info(f" Contract record created with ID: {new_contract.id}")
        
        # Create upload directory for this contract
        upload_base = FilePath(settings.UPLOAD_DIR)
        contract_upload_dir = upload_base / "contracts" / str(new_contract.id)
        contract_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = contract_upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f" File saved to: {file_path}")
        
        # 🔥 EXTRACT ACTUAL TEXT CONTENT FROM DOCUMENT
        logger.info(f" Extracting text from {file_ext} file...")
        extracted_text = DocumentParser.extract_text(str(file_path))
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            logger.warning(f" No text extracted from file, using placeholder")
            extracted_text = f"Unable to extract text from {file.filename}. Please check the file format."
        else:
            logger.info(f" Extracted {len(extracted_text)} characters from document")
        
        # Convert extracted text to HTML format with styling
        file_size_kb = len(content) / 1024
        file_url = f"uploads/contracts/{new_contract.id}/{file.filename}"
        
        # Format the extracted content as HTML
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
        
        # Create first version with extracted content
        contract_version = ContractVersion(
            contract_id=new_contract.id,
            version_number=1,
            version_type="draft",
            contract_content=html_content,  # 🔥 ACTUAL EXTRACTED CONTENT IN HTML FORMAT
            contract_content_ar=None,
            change_summary=f"Initial upload: {file.filename} - {len(extracted_text):,} characters extracted",
            created_by=current_user.id
        )
        
        db.add(contract_version)
        db.commit()
        db.refresh(new_contract)
        
        logger.info(f" Contract uploaded successfully: {contract_number}")
        logger.info(f" Content extracted: {len(extracted_text):,} characters")
        
        return {
            "id": new_contract.id,
            "contract_number": contract_number,
            "contract_title": contract_title,
            "status": "draft",
            "file_path": str(file_path),
            "file_url": file_url,
            "file_name": file.filename,
            "file_size": len(content),
            "file_type": file_ext[1:],
            "content_length": len(extracted_text),
            "content_extracted": len(extracted_text) > 10,
            "message": f"Contract uploaded successfully. Extracted {len(extracted_text):,} characters from document."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload contract: {str(e)}"
        )

@router.post("/generate-with-ai", response_model=ContractResponse)
def generate_contract_with_ai(
    contract_data: dict,  # Include AI generation parameters
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate contract using AI with specified clauses"""
    
    # Generate contract number
    year = datetime.now().year
    count = db.query(Contract).filter(
        Contract.contract_number.like(f"CNT-{year}-%")
    ).count()
    contract_number = f"CNT-{year}-{count + 1:04d}"
    
    # Create contract
    new_contract = Contract(
        contract_number=contract_number,
        contract_title=contract_data.get("contract_title", "AI Generated Contract"),
        contract_title_ar=contract_data.get("contract_title_ar"),
        contract_type=contract_data.get("contract_type"),
        profile_type=contract_data.get("profile_type"),
        contract_value=contract_data.get("contract_value"),
        currency=contract_data.get("currency", "QAR"),
        start_date=contract_data.get("start_date"),
        end_date=contract_data.get("end_date"),
        status="draft",
        current_version=1,
        created_by=current_user.id
    )
    
    db.add(new_contract)
    db.flush()
    
    # TODO: Call AI service to generate contract content
    # For now, create placeholder content based on selected clauses
    ai_clauses = contract_data.get("ai_clauses", {})
    
    ai_generated_content = f"""
    <h1>{contract_data.get('contract_title', 'AI Generated Contract')}</h1>
    <p><strong>Contract Number:</strong> {contract_number}</p>
    <p><strong>Generated Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
    
    <h2>Terms and Conditions</h2>
    """
    
    # Add clauses based on AI selections
    if ai_clauses.get("performance_bond"):
        ai_generated_content += "<h3>Performance Bond</h3><p>The contractor shall provide a performance bond...</p>"
    
    if ai_clauses.get("retention_amount"):
        ai_generated_content += "<h3>Retention Amount</h3><p>A retention amount shall be withheld...</p>"
    
    # Add more clauses as needed
    
    # Create first version with AI-generated content
    contract_version = ContractVersion(
        contract_id=new_contract.id,
        version_number=1,
        version_type="ai_generated",
        contract_content=ai_generated_content,  # AI GENERATED CONTENT
        contract_content_ar=None,  # TODO: Generate Arabic version
        change_summary="Contract generated using AI with selected clauses",
        created_by=current_user.id
    )
    
    db.add(contract_version)
    db.commit()
    db.refresh(new_contract)
    
    return new_contract




class CommentCreate(BaseModel):
    contract_id: int
    comment_text: str
    selected_text: Optional[str] = None

# GET ALL COMMENTS
@router.get("/comments/{contract_id}")
async def get_comments(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        query = text("""
            SELECT 
                cc.id, cc.contract_id, cc.user_id,
                CONCAT(u.first_name, ' ', u.last_name) as author,
                cc.comment_text, cc.selected_text,
                cc.created_at, cc.updated_at
            FROM contract_comments cc
            INNER JOIN users u ON cc.user_id = u.id
            WHERE cc.contract_id = :contract_id
            ORDER BY cc.created_at DESC
        """)
        
        result = db.execute(query, {"contract_id": contract_id})
        rows = result.fetchall()
        
        comments = []
        for row in rows:
            comments.append({
                "id": row[0],
                "contract_id": row[1],
                "user_id": row[2],
                "author": row[3] or "Unknown",
                "comment_text": row[4],
                "selected_text": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None
            })
        
        return {"success": True, "comments": comments}
        
    except Exception as e:
        logger.error(f"Error fetching comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ADD COMMENT
@router.post("/comments/add")
async def add_comment(
    req: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Verify contract access
        check = text("SELECT id FROM contracts WHERE id = :cid AND company_id = :company")
        result = db.execute(check, {"cid": req.contract_id, "company": current_user.company_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Insert comment
        insert = text("""
            INSERT INTO contract_comments 
            (contract_id, user_id, comment_text, selected_text, created_at, updated_at)
            VALUES (:cid, :uid, :text, :selected, NOW(), NOW())
        """)
        
        db.execute(insert, {
            "cid": req.contract_id,
            "uid": current_user.id,
            "text": req.comment_text,
            "selected": req.selected_text
        })
        db.commit()
        
        # Get inserted ID
        comment_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        
        # Get full comment
        get_comment = text("""
            SELECT 
                cc.id, cc.contract_id, cc.user_id,
                CONCAT(u.first_name, ' ', u.last_name) as author,
                cc.comment_text, cc.selected_text,
                cc.created_at, cc.updated_at
            FROM contract_comments cc
            INNER JOIN users u ON cc.user_id = u.id
            WHERE cc.id = :id
        """)
        
        row = db.execute(get_comment, {"id": comment_id}).fetchone()
        
        return {
            "success": True,
            "comment_id": comment_id,
            "comment": {
                "id": row[0],
                "contract_id": row[1],
                "user_id": row[2],
                "author": row[3],
                "comment_text": row[4],
                "selected_text": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "updated_at": row[7].isoformat() if row[7] else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# DELETE COMMENT - WITH OWNERSHIP CHECK
@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Check ownership
        check = text("""
            SELECT cc.user_id, c.company_id
            FROM contract_comments cc
            INNER JOIN contracts c ON cc.contract_id = c.id
            WHERE cc.id = :id
        """)
        
        result = db.execute(check, {"id": comment_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        comment_user_id = row[0]
        company_id = row[1]
        
        # Verify company access
        if company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # CRITICAL: Verify ownership
        if comment_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only delete your own comments")
        
        # Delete
        delete = text("DELETE FROM contract_comments WHERE id = :id")
        db.execute(delete, {"id": comment_id})
        db.commit()
        
        return {"success": True, "message": "Comment deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        