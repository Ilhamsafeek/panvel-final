# =====================================================
# FILE: app/api/api_v1/obligations/obligations.py
# Complete Obligations API with AI Generation
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging
import json
import re

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.obligation import Obligation, ObligationTracking
from app.models.contract import Contract

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/obligations", tags=["obligations"])

# =====================================================
# PYDANTIC SCHEMAS
# =====================================================

class ObligationCreate(BaseModel):
    contract_id: int
    obligation_title: str
    description: Optional[str] = None
    obligation_type: Optional[str] = None
    owner_user_id: Optional[int] = None
    escalation_user_id: Optional[int] = None
    threshold_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = "initiated"
    is_ai_generated: Optional[bool] = False

class ObligationUpdate(BaseModel):
    obligation_title: Optional[str] = None
    description: Optional[str] = None
    obligation_type: Optional[str] = None
    owner_user_id: Optional[int] = None
    escalation_user_id: Optional[int] = None
    threshold_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None

class ObligationResponse(BaseModel):
    id: int
    contract_id: int
    obligation_title: str
    description: Optional[str]
    obligation_type: Optional[str]
    owner_user_id: Optional[int]
    escalation_user_id: Optional[int]
    threshold_date: Optional[datetime]
    due_date: Optional[datetime]
    status: str
    is_ai_generated: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AIObligationResponse(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    confidence: float
    clause_reference: Optional[str] = None

# =====================================================
# GET CONTRACT OBLIGATIONS
# =====================================================

@router.get("/contract/{contract_id}", response_model=List[ObligationResponse])
async def get_contract_obligations(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all obligations for a specific contract"""
    try:
        logger.info(f"📋 Fetching obligations for contract {contract_id}")
        
        obligations = db.query(Obligation).filter(
            Obligation.contract_id == contract_id
        ).order_by(Obligation.created_at.desc()).all()
        
        logger.info(f"✅ Found {len(obligations)} obligations")
        
        # Enrich with user data
        enriched_obligations = []
        for obligation in obligations:
            # Get contract info
            contract = db.query(Contract).filter(Contract.id == obligation.contract_id).first()
            
            # Get owner info
            owner = None
            if obligation.owner_user_id:
                owner = db.query(User).filter(User.id == obligation.owner_user_id).first()
            
            # Get escalation user info
            escalation_user = None
            if obligation.escalation_user_id:
                escalation_user = db.query(User).filter(User.id == obligation.escalation_user_id).first()
            
            enriched_data = {
                "id": obligation.id,
                "contract_id": obligation.contract_id,
                "contract_number": contract.contract_number if contract else None,
                "contract_title": contract.contract_title if contract else None,
                "obligation_title": obligation.obligation_title,
                "description": obligation.description,
                "obligation_type": obligation.obligation_type or "other",
                "owner_user_id": obligation.owner_user_id,
                "owner_name": f"{owner.first_name} {owner.last_name}" if owner else None,
                "owner_email": owner.email if owner else None,
                "escalation_user_id": obligation.escalation_user_id,
                "escalation_name": f"{escalation_user.first_name} {escalation_user.last_name}" if escalation_user else None,
                "threshold_date": obligation.threshold_date,
                "due_date": obligation.due_date,
                "status": obligation.status or "initiated",
                "is_ai_generated": obligation.is_ai_generated,
                "created_at": obligation.created_at,
                "updated_at": obligation.updated_at
            }
            enriched_obligations.append(enriched_data)
        
        return enriched_obligations
        
    except Exception as e:
        logger.error(f"❌ Error fetching obligations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# =====================================================
# AI OBLIGATION GENERATION
# =====================================================

@router.post("/generate-ai/{contract_id}", response_model=List[AIObligationResponse])
async def generate_ai_obligations(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate obligations using Claude AI by analyzing the actual contract document.
    """
    try:
        # Verify contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        logger.info(f"🤖 Generating AI obligations for contract {contract_id}")
        
        # Get contract content from contract_versions table
        contract_text = await get_contract_content(contract_id, db)
        
        if not contract_text or len(contract_text.strip()) < 100:
            raise HTTPException(
                status_code=400, 
                detail="Contract content is too short or empty. Please ensure the contract has been created with content."
            )
        
        logger.info(f"📄 Contract content length: {len(contract_text)} characters")
        
        # Extract obligations using Claude AI
        ai_obligations = await extract_obligations_with_ai(contract_text, contract)
        
        logger.info(f"✅ Generated {len(ai_obligations)} AI obligations")
        return ai_obligations
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating AI obligations: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate obligations: {str(e)}"
        )

async def get_contract_content(contract_id: int, db: Session) -> str:
    """
    Retrieve the actual contract content from contract_versions table.
    """
    try:
        # Get the latest version of the contract content
        query = text("""
            SELECT contract_content, contract_content_ar
            FROM contract_versions
            WHERE contract_id = :contract_id
            ORDER BY version_number DESC
            LIMIT 1
        """)
        
        result = db.execute(query, {"contract_id": contract_id}).fetchone()
        
        if result and result.contract_content:
            content = result.contract_content
            logger.info(f"✅ Retrieved contract content from database")
            return content
        
        # Fallback: Get contract metadata
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise Exception("Contract not found")
        
        # Build contract info from metadata
        contract_info = f"""
CONTRACT INFORMATION:

Contract Number: {contract.contract_number}
Contract Title: {getattr(contract, 'contract_title', 'N/A')}
Contract Type: {getattr(contract, 'contract_type', 'N/A')}

PARTIES:
Party A: {getattr(contract, 'party_a_name', 'N/A')}
Party B: {getattr(contract, 'party_b_name', 'N/A')}

DURATION:
Start Date: {getattr(contract, 'start_date', 'N/A')}
End Date: {getattr(contract, 'end_date', 'N/A')}

FINANCIAL:
Contract Value: {getattr(contract, 'contract_value', 'N/A')} {getattr(contract, 'currency', 'QAR')}

SCOPE:
This is a {getattr(contract, 'contract_type', 'service')} agreement between the parties for the execution of contracted services and deliverables as per agreed terms and conditions.
"""
        
        logger.info(f"⚠️ Using contract metadata as content is not available")
        return contract_info
        
    except Exception as e:
        logger.error(f"❌ Error reading contract content: {str(e)}")
        raise Exception(f"Failed to retrieve contract content: {str(e)}")

async def extract_obligations_with_ai(contract_text: str, contract) -> List[AIObligationResponse]:
    """
    Use Claude AI to extract obligations from the actual contract text.
    """
    try:
        from app.services.claude_service import claude_service
        
        # Create comprehensive AI prompt
        prompt = f"""Analyze this contract and extract ALL contractual obligations, duties, requirements, and commitments. Return ONLY a valid JSON array.

CONTRACT TEXT:
{contract_text[:8000]}

TASK: Extract every obligation, duty, requirement, or commitment mentioned in this contract.

For each obligation found, create a JSON object with these exact fields:
- title: Short descriptive title (max 100 chars)
- description: Detailed explanation of what must be done (max 500 chars)
- category: Choose ONE from: payment, delivery, compliance, reporting, maintenance, insurance, coordination, inspection, other
- priority: Choose ONE from: high, medium, low (high = financial/critical, medium = operational, low = administrative)
- confidence: Number between 0.5 and 1.0 indicating AI confidence
- clause_reference: Where in the contract this obligation appears (optional)

CRITICAL INSTRUCTIONS:
1. Extract AT LEAST 5 obligations even if the contract is brief
2. Look for: payment terms, delivery requirements, reporting duties, compliance rules, maintenance obligations, insurance requirements, meeting schedules, approval processes, coordination responsibilities, inspection requirements
3. If the contract mentions parties, dates, amounts, or actions - those are obligations
4. Return ONLY the JSON array, no other text or markdown
5. Do NOT wrap in code blocks or markdown

EXAMPLE OUTPUT FORMAT (return similar structure):
[
  {{"title": "Monthly Payment Obligation", "description": "Pay invoice within 30 days of receipt", "category": "payment", "priority": "high", "confidence": 0.95, "clause_reference": "Payment Terms - Clause 5.1"}},
  {{"title": "Quality Report Submission", "description": "Submit monthly quality reports by the 5th of each month", "category": "reporting", "priority": "medium", "confidence": 0.88, "clause_reference": "Reporting Requirements"}}
]

Now extract obligations from the contract above and return ONLY the JSON array:"""

        logger.info(f"🤖 Calling Claude AI via ClaudeService")
        logger.info(f"📝 Contract text length: {len(contract_text)} characters")
        
        # Call Claude AI
        message = claude_service.client.messages.create(
            model=claude_service.model,
            max_tokens=4000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract response
        response_text = message.content[0].text
        
        logger.info(f"📨 Received AI response: {len(response_text)} characters")
        logger.info(f"📄 Raw response preview: {response_text[:300]}")
        
        # Clean and parse JSON
        response_text = response_text.strip()
        
        # Remove markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        response_text = response_text.strip()
        
        logger.info(f"🧹 Cleaned response: {response_text[:200]}")
        
        # Parse JSON
        try:
            obligations_data = json.loads(response_text)
        except json.JSONDecodeError as je:
            logger.error(f"❌ JSON parsing failed: {str(je)}")
            logger.error(f"📄 Full response: {response_text}")
            
            # Try to extract JSON array from text using regex
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                try:
                    obligations_data = json.loads(json_match.group(0))
                    logger.info(f"✅ Extracted JSON from text using regex")
                except:
                    raise Exception("Failed to parse AI response as JSON")
            else:
                raise Exception("AI response does not contain valid JSON array")
        
        # Validate and convert to response objects
        result = []
        for obl in obligations_data:
            try:
                result.append(AIObligationResponse(
                    title=str(obl.get("title", ""))[:100],
                    description=str(obl.get("description", ""))[:500],
                    category=str(obl.get("category", "other")),
                    priority=str(obl.get("priority", "medium")),
                    confidence=float(obl.get("confidence", 0.8)),
                    clause_reference=obl.get("clause_reference")
                ))
            except Exception as e:
                logger.warning(f"⚠️ Skipping invalid obligation: {str(e)}")
                continue
        
        if len(result) == 0:
            raise Exception("No valid obligations extracted from AI response")
        
        logger.info(f"✅ Successfully parsed {len(result)} obligations")
        return result
        
    except ImportError:
        logger.error("❌ Claude service not available")
        raise Exception("AI service is not configured. Please configure Claude API key.")
    except Exception as e:
        logger.error(f"❌ Error in AI extraction: {str(e)}")
        raise Exception(f"AI obligation extraction failed: {str(e)}")

# =====================================================
# CREATE OBLIGATION
# =====================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_obligation(
    obligation: ObligationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new obligation"""
    try:
        logger.info(f"➕ Creating obligation: {obligation.obligation_title}")
        
        # Verify contract exists
        contract = db.query(Contract).filter(Contract.id == obligation.contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Create obligation
        new_obligation = Obligation(
            contract_id=obligation.contract_id,
            obligation_title=obligation.obligation_title,
            description=obligation.description,
            obligation_type=obligation.obligation_type,
            owner_user_id=obligation.owner_user_id,
            escalation_user_id=obligation.escalation_user_id,
            threshold_date=obligation.threshold_date,
            due_date=obligation.due_date,
            status=obligation.status,
            is_ai_generated=obligation.is_ai_generated,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_obligation)
        db.commit()
        db.refresh(new_obligation)
        
        logger.info(f"✅ Obligation created with ID: {new_obligation.id}")
        
        return {
            "success": True,
            "message": "Obligation created successfully",
            "id": new_obligation.id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating obligation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# =====================================================
# UPDATE OBLIGATION
# =====================================================

@router.put("/{obligation_id}")
async def update_obligation(
    obligation_id: int,
    obligation_update: ObligationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing obligation"""
    try:
        logger.info(f"🔄 Updating obligation {obligation_id}")
        
        obligation = db.query(Obligation).filter(Obligation.id == obligation_id).first()
        if not obligation:
            raise HTTPException(status_code=404, detail="Obligation not found")
        
        # Track changes
        changes = []
        
        if obligation_update.obligation_title is not None:
            obligation.obligation_title = obligation_update.obligation_title
            changes.append("Title updated")
            
        if obligation_update.description is not None:
            obligation.description = obligation_update.description
            changes.append("Description updated")
            
        if obligation_update.obligation_type is not None:
            obligation.obligation_type = obligation_update.obligation_type
            changes.append("Type updated")
            
        if obligation_update.owner_user_id is not None:
            obligation.owner_user_id = obligation_update.owner_user_id
            changes.append("Owner updated")
            
        if obligation_update.escalation_user_id is not None:
            obligation.escalation_user_id = obligation_update.escalation_user_id
            changes.append("Escalation updated")
            
        if obligation_update.threshold_date is not None:
            obligation.threshold_date = obligation_update.threshold_date
            changes.append("Threshold date updated")
            
        if obligation_update.due_date is not None:
            obligation.due_date = obligation_update.due_date
            changes.append("Due date updated")
            
        if obligation_update.status is not None:
            obligation.status = obligation_update.status
            changes.append("Status updated")
        
        obligation.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(obligation)
        
        # Create tracking log
        if changes:
            tracking = ObligationTracking(
                obligation_id=obligation.id,
                action_taken="Updated",
                action_by=current_user.id,
                notes="; ".join(changes),
                created_at=datetime.utcnow()
            )
            db.add(tracking)
            db.commit()
        
        logger.info(f"✅ Obligation {obligation_id} updated")
        
        return {
            "success": True,
            "message": "Obligation updated successfully",
            "changes": changes
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error updating obligation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# =====================================================
# DELETE OBLIGATION
# =====================================================

@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an obligation and all related records"""
    try:
        logger.info(f"🗑️ Deleting obligation {obligation_id}")
        
        obligation = db.query(Obligation).filter(Obligation.id == obligation_id).first()
        if not obligation:
            raise HTTPException(status_code=404, detail="Obligation not found")
        
        # Disable foreign key checks temporarily (MySQL specific)
        try:
            db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            logger.info(f"  ⚙️ Disabled foreign key checks")
            
            # Delete from all related tables
            tables_to_clean = [
                'obligation_tracking',
                'obligation_updates',
                'obligation_escalations',
                'obligation_reminders',
                'obligation_attachments'
            ]
            
            for table in tables_to_clean:
                try:
                    result = db.execute(
                        text(f"DELETE FROM {table} WHERE obligation_id = :id"), 
                        {"id": obligation_id}
                    )
                    deleted_count = result.rowcount
                    if deleted_count > 0:
                        logger.info(f"  ✅ Deleted {deleted_count} records from {table}")
                except Exception as e:
                    # Table might not exist or no records, continue
                    logger.info(f"  ⚠️ {table}: {str(e)}")
                    continue
            
            # Now delete the obligation itself
            db.execute(text("DELETE FROM obligations WHERE id = :id"), {"id": obligation_id})
            logger.info(f"  ✅ Deleted obligation {obligation_id}")
            
            # Re-enable foreign key checks
            db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            logger.info(f"  ⚙️ Re-enabled foreign key checks")
            
            # Commit all changes
            db.commit()
            
            logger.info(f"✅ Obligation {obligation_id} and all related records deleted successfully")
        
        except Exception as e:
            # Make sure to re-enable foreign key checks even if error occurs
            try:
                db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                db.commit()
            except:
                pass
            raise e
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error deleting obligation: {str(e)}")
        
        # Check if it's a foreign key error
        error_message = str(e)
        if "foreign key constraint" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete this obligation because it has related records. Please contact support for assistance."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete obligation: {str(e)}"
        )