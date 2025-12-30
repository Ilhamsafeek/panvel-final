# =====================================================
# FILE: app/api/api_v1/obligations/obligations.py
# COMPLETE OBLIGATION MANAGEMENT API
# MATCHES EXISTING DATABASE SCHEMA
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import logging
import json

from app.core.database import get_db
from app.models.user import User
from app.models.contract import Contract
from app.models.obligation import Obligation, ObligationTracking
from app.core.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# =====================================================
# PYDANTIC SCHEMAS
# =====================================================

class ObligationCreate(BaseModel):
    contract_id: int
    obligation_title: str
    description: Optional[str] = None
    obligation_type: Optional[str] = "other"
    owner_user_id: Optional[int] = None
    escalation_user_id: Optional[int] = None
    threshold_date: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "initiated"
    is_ai_generated: Optional[bool] = False

class ObligationUpdate(BaseModel):
    obligation_title: Optional[str] = None
    description: Optional[str] = None
    obligation_type: Optional[str] = None
    owner_user_id: Optional[int] = None
    escalation_user_id: Optional[int] = None
    threshold_date: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime object"""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None

def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO string"""
    if not dt:
        return None
    return dt.isoformat()


# =====================================================
# 1. CREATE OBLIGATION
# =====================================================

@router.post("/", response_model=Dict[str, Any])
async def create_obligation(
    request: ObligationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new obligation"""
    try:
        logger.info(f" Creating obligation for contract {request.contract_id}")
        
        # Verify contract exists and belongs to user's company
        contract = db.query(Contract).filter(
            Contract.id == request.contract_id,
            Contract.company_id == current_user.company_id
        ).first()
        
        if not contract:
            logger.error(f" Contract {request.contract_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )
        
        # Parse dates
        threshold_date = parse_date(request.threshold_date)
        due_date = parse_date(request.due_date)
        
        # Use raw SQL INSERT to match existing table schema exactly
        insert_query = text("""
            INSERT INTO obligations (
                contract_id, obligation_title, description, obligation_type,
                owner_user_id, escalation_user_id, threshold_date, due_date,
                status, is_ai_generated, is_preset, created_at, updated_at
            ) VALUES (
                :contract_id, :obligation_title, :description, :obligation_type,
                :owner_user_id, :escalation_user_id, :threshold_date, :due_date,
                :status, :is_ai_generated, :is_preset, :created_at, :updated_at
            )
        """)
        
        now = datetime.utcnow()
        
        db.execute(insert_query, {
            "contract_id": request.contract_id,
            "obligation_title": request.obligation_title,
            "description": request.description,
            "obligation_type": request.obligation_type or "other",
            "owner_user_id": request.owner_user_id if request.owner_user_id else None,
            "escalation_user_id": request.escalation_user_id if request.escalation_user_id else None,
            "threshold_date": threshold_date,
            "due_date": due_date,
            "status": request.status or "initiated",
            "is_ai_generated": 1 if request.is_ai_generated else 0,
            "is_preset": 0,
            "created_at": now,
            "updated_at": now
        })
        
        db.commit()
        
        # Get the inserted ID
        result = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
        new_id = result[0] if result else None
        
        logger.info(f" Created obligation ID: {new_id}")
        
        return {
            "success": True,
            "message": "Obligation created successfully",
            "id": new_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error creating obligation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create obligation: {str(e)}"
        )


# =====================================================
# 2. GET ALL OBLIGATIONS (with filters)
# =====================================================

@router.get("/")
async def get_obligations(
    contract_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all obligations with optional filters"""
    try:
        logger.info(f"📋 Fetching obligations for user {current_user.id}, contract: {contract_id}")
        
        query = """
            SELECT 
                o.id,
                o.contract_id,
                o.obligation_title,
                o.description,
                o.obligation_type,
                o.owner_user_id,
                o.escalation_user_id,
                o.threshold_date,
                o.due_date,
                o.status,
                o.is_ai_generated,
                o.is_preset,
                o.created_at,
                o.updated_at,
                CONCAT(owner.first_name, ' ', owner.last_name) as owner_name,
                CONCAT(esc.first_name, ' ', esc.last_name) as escalation_name,
                c.contract_title,
                c.contract_number
            FROM obligations o
            INNER JOIN contracts c ON o.contract_id = c.id
            LEFT JOIN users owner ON o.owner_user_id = owner.id
            LEFT JOIN users esc ON o.escalation_user_id = esc.id
            WHERE c.company_id = :company_id
        """
        
        params = {"company_id": current_user.company_id}
        
        if contract_id:
            query += " AND o.contract_id = :contract_id"
            params["contract_id"] = contract_id
        
        if status_filter and status_filter != 'all':
            query += " AND o.status = :status"
            params["status"] = status_filter
        
        query += " ORDER BY o.created_at DESC"
        
        result = db.execute(text(query), params)
        rows = result.fetchall()
        
        obligations = []
        for row in rows:
            obligations.append({
                "id": row[0],
                "contract_id": row[1],
                "obligation_title": row[2],
                "description": row[3],
                "obligation_type": row[4],
                "owner_user_id": row[5],
                "escalation_user_id": row[6],
                "threshold_date": format_datetime(row[7]),
                "due_date": format_datetime(row[8]),
                "status": row[9] or "initiated",
                "is_ai_generated": bool(row[10]),
                "is_preset": bool(row[11]),
                "created_at": format_datetime(row[12]),
                "updated_at": format_datetime(row[13]),
                "owner_name": row[14],
                "escalation_name": row[15],
                "contract_title": row[16],
                "contract_number": row[17]
            })
        
        logger.info(f" Found {len(obligations)} obligations")
        return obligations
        
    except Exception as e:
        logger.error(f" Error fetching obligations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch obligations: {str(e)}"
        )


# =====================================================
# 3. GET SINGLE OBLIGATION
# =====================================================

@router.get("/{obligation_id}")
async def get_obligation(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single obligation by ID"""
    try:
        query = """
            SELECT 
                o.id,
                o.contract_id,
                o.obligation_title,
                o.description,
                o.obligation_type,
                o.owner_user_id,
                o.escalation_user_id,
                o.threshold_date,
                o.due_date,
                o.status,
                o.is_ai_generated,
                o.created_at,
                o.updated_at,
                CONCAT(owner.first_name, ' ', owner.last_name) as owner_name,
                CONCAT(esc.first_name, ' ', esc.last_name) as escalation_name
            FROM obligations o
            INNER JOIN contracts c ON o.contract_id = c.id
            LEFT JOIN users owner ON o.owner_user_id = owner.id
            LEFT JOIN users esc ON o.escalation_user_id = esc.id
            WHERE o.id = :obligation_id AND c.company_id = :company_id
        """
        
        result = db.execute(text(query), {
            "obligation_id": obligation_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Obligation not found"
            )
        
        return {
            "id": result[0],
            "contract_id": result[1],
            "obligation_title": result[2],
            "description": result[3],
            "obligation_type": result[4],
            "owner_user_id": result[5],
            "escalation_user_id": result[6],
            "threshold_date": format_datetime(result[7]),
            "due_date": format_datetime(result[8]),
            "status": result[9] or "initiated",
            "is_ai_generated": bool(result[10]),
            "created_at": format_datetime(result[11]),
            "updated_at": format_datetime(result[12]),
            "owner_name": result[13],
            "escalation_name": result[14]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error fetching obligation {obligation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch obligation: {str(e)}"
        )


# =====================================================
# 4. UPDATE OBLIGATION
# =====================================================

@router.put("/{obligation_id}")
async def update_obligation(
    obligation_id: int,
    request: ObligationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing obligation"""
    try:
        logger.info(f" Updating obligation {obligation_id}")
        
        # Verify obligation exists and belongs to user's company
        check_query = """
            SELECT o.id FROM obligations o
            INNER JOIN contracts c ON o.contract_id = c.id
            WHERE o.id = :obligation_id AND c.company_id = :company_id
        """
        result = db.execute(text(check_query), {
            "obligation_id": obligation_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Obligation not found"
            )
        
        # Build dynamic update query
        update_fields = []
        params = {"obligation_id": obligation_id}
        
        if request.obligation_title is not None:
            update_fields.append("obligation_title = :title")
            params["title"] = request.obligation_title
        
        if request.description is not None:
            update_fields.append("description = :description")
            params["description"] = request.description
        
        if request.obligation_type is not None:
            update_fields.append("obligation_type = :type")
            params["type"] = request.obligation_type
        
        if request.owner_user_id is not None:
            update_fields.append("owner_user_id = :owner_id")
            params["owner_id"] = request.owner_user_id if request.owner_user_id else None
        
        if request.escalation_user_id is not None:
            update_fields.append("escalation_user_id = :escalation_id")
            params["escalation_id"] = request.escalation_user_id if request.escalation_user_id else None
        
        if request.threshold_date is not None:
            update_fields.append("threshold_date = :threshold")
            params["threshold"] = parse_date(request.threshold_date)
        
        if request.due_date is not None:
            update_fields.append("due_date = :due_date")
            params["due_date"] = parse_date(request.due_date)
        
        if request.status is not None:
            update_fields.append("status = :status")
            params["status"] = request.status
        
        update_fields.append("updated_at = :updated_at")
        params["updated_at"] = datetime.utcnow()
        
        if update_fields:
            update_query = f"""
                UPDATE obligations 
                SET {', '.join(update_fields)}
                WHERE id = :obligation_id
            """
            db.execute(text(update_query), params)
            db.commit()
        
        logger.info(f" Updated obligation {obligation_id}")
        
        return {
            "success": True,
            "message": "Obligation updated successfully",
            "id": obligation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error updating obligation {obligation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update obligation: {str(e)}"
        )


# =====================================================
# 5. DELETE OBLIGATION
# =====================================================

@router.delete("/{obligation_id}")
async def delete_obligation(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an obligation"""
    try:
        logger.info(f"🗑️ Deleting obligation {obligation_id}")
        
        # Verify obligation exists and belongs to user's company
        check_query = """
            SELECT o.id FROM obligations o
            INNER JOIN contracts c ON o.contract_id = c.id
            WHERE o.id = :obligation_id AND c.company_id = :company_id
        """
        result = db.execute(text(check_query), {
            "obligation_id": obligation_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Obligation not found"
            )
        
        # Delete ALL related records from child tables first
        # 1. Delete from obligation_updates
        try:
            db.execute(
                text("DELETE FROM obligation_updates WHERE obligation_id = :id"),
                {"id": obligation_id}
            )
            logger.info(f"  ✓ Deleted obligation_updates for {obligation_id}")
        except Exception as e:
            logger.warning(f"  ⚠ obligation_updates: {str(e)}")
        
        # 2. Delete from obligation_tracking
        try:
            db.execute(
                text("DELETE FROM obligation_tracking WHERE obligation_id = :id"),
                {"id": obligation_id}
            )
            logger.info(f"  ✓ Deleted obligation_tracking for {obligation_id}")
        except Exception as e:
            logger.warning(f"  ⚠ obligation_tracking: {str(e)}")
        
        # 3. Delete from obligation_escalations
        try:
            db.execute(
                text("DELETE FROM obligation_escalations WHERE obligation_id = :id"),
                {"id": obligation_id}
            )
            logger.info(f"  ✓ Deleted obligation_escalations for {obligation_id}")
        except Exception as e:
            logger.warning(f"  ⚠ obligation_escalations: {str(e)}")
        
        # 4. Commit child deletions
        db.commit()
        
        # 5. Now delete the main obligation record
        db.execute(
            text("DELETE FROM obligations WHERE id = :id"),
            {"id": obligation_id}
        )
        
        db.commit()
        logger.info(f" Successfully deleted obligation {obligation_id}")
        
        return {
            "success": True,
            "message": "Obligation deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error deleting obligation {obligation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete obligation: {str(e)}"
        )


# =====================================================
# 6. GENERATE AI OBLIGATIONS
# =====================================================

@router.post("/generate-ai/{contract_id}")
async def generate_ai_obligations(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Use AI to extract obligations from contract content"""
    try:
        logger.info(f" Generating AI obligations for contract {contract_id}")
        
        # Verify contract exists and belongs to user's company
        contract = db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.company_id == current_user.company_id
        ).first()
        
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )
        
        # Get contract content from latest version
        version_query = """
            SELECT contract_content FROM contract_versions 
            WHERE contract_id = :contract_id 
            ORDER BY version_number DESC 
            LIMIT 1
        """
        result = db.execute(text(version_query), {"contract_id": contract_id}).fetchone()
        
        contract_content = result[0] if result else None
        
        if not contract_content:
            logger.warning(f" No contract content found for contract {contract_id}")
            return generate_fallback_obligations(contract.contract_type)
        
        # Try to use Claude API for extraction
        try:
            from app.services.claude_service import ClaudeService
            claude_service = ClaudeService()
            
            if claude_service.client:
                obligations = await extract_with_claude(
                    claude_service, 
                    contract_content, 
                    contract.contract_type
                )
                if obligations:
                    return obligations
        except Exception as e:
            logger.warning(f" Claude API not available: {str(e)}")
        
        # Fallback to pattern-based extraction
        return generate_fallback_obligations(contract.contract_type)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error generating AI obligations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate obligations: {str(e)}"
        )


async def extract_with_claude(claude_service, contract_content: str, contract_type: str) -> List[Dict]:
    """Extract obligations using Claude AI"""
    prompt = f"""Analyze this {contract_type} contract and extract ALL contractual obligations.

For each obligation, provide:
1. **title**: Clear obligation title (max 50 words)
2. **description**: Detailed description (max 150 words)
3. **type**: One of [payment, deliverable, compliance, reporting, insurance, performance, coordination, indemnification, timely_completion, other]

Contract Content:
{contract_content[:8000]}

Return ONLY a valid JSON array. No markdown, no explanation, just the JSON array starting with [ and ending with ].
Example format:
[
  {{"title": "Payment Terms", "description": "Pay within 30 days...", "type": "payment"}},
  {{"title": "Delivery", "description": "Deliver by...", "type": "deliverable"}}
]"""

    try:
        response = claude_service.client.messages.create(
            model=claude_service.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Clean response
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        obligations = json.loads(response_text)
        return obligations if isinstance(obligations, list) else []
    except Exception as e:
        logger.error(f"Claude extraction error: {str(e)}")
        return []


def generate_fallback_obligations(contract_type: str) -> List[Dict]:
    """Generate fallback obligations based on contract type"""
    
    base_obligations = [
        {
            "title": "Timely Completion",
            "description": "Deliver work within the agreed timeline and notify of any potential delays promptly.",
            "type": "timely_completion"
        },
        {
            "title": "Quality Standards Compliance",
            "description": "Ensure all work meets industry standards and specific quality requirements outlined in the agreement.",
            "type": "compliance"
        },
        {
            "title": "Payment Terms",
            "description": "Process payments according to the agreed schedule and terms specified in the contract.",
            "type": "payment"
        },
        {
            "title": "Reporting Requirements",
            "description": "Provide regular progress updates and reports on work completion and any issues encountered.",
            "type": "reporting"
        },
        {
            "title": "Compliance with Laws",
            "description": "Follow all applicable laws, regulations, and safety standards relevant to the work being performed.",
            "type": "compliance"
        }
    ]
    
    # Add type-specific obligations
    if contract_type and 'service' in contract_type.lower():
        base_obligations.append({
            "title": "Service Level Agreement",
            "description": "Maintain service levels as specified in the SLA, including response times and availability.",
            "type": "performance"
        })
    
    if contract_type and 'construction' in contract_type.lower():
        base_obligations.extend([
            {
                "title": "Insurance Coverage",
                "description": "Maintain appropriate insurance coverage including liability and workers' compensation.",
                "type": "insurance"
            },
            {
                "title": "Safety Standards",
                "description": "Comply with all site safety requirements and maintain a safe working environment.",
                "type": "compliance"
            }
        ])
    
    return base_obligations


# =====================================================
# 7. BULK OPERATIONS
# =====================================================

@router.post("/bulk-create")
async def bulk_create_obligations(
    obligations: List[ObligationCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create multiple obligations at once"""
    try:
        created_count = 0
        errors = []
        now = datetime.utcnow()
        
        insert_query = text("""
            INSERT INTO obligations (
                contract_id, obligation_title, description, obligation_type,
                owner_user_id, escalation_user_id, threshold_date, due_date,
                status, is_ai_generated, is_preset, created_at, updated_at
            ) VALUES (
                :contract_id, :obligation_title, :description, :obligation_type,
                :owner_user_id, :escalation_user_id, :threshold_date, :due_date,
                :status, :is_ai_generated, :is_preset, :created_at, :updated_at
            )
        """)
        
        for i, obl in enumerate(obligations):
            try:
                # Verify contract
                contract = db.query(Contract).filter(
                    Contract.id == obl.contract_id,
                    Contract.company_id == current_user.company_id
                ).first()
                
                if not contract:
                    errors.append(f"Item {i}: Contract not found")
                    continue
                
                db.execute(insert_query, {
                    "contract_id": obl.contract_id,
                    "obligation_title": obl.obligation_title,
                    "description": obl.description,
                    "obligation_type": obl.obligation_type or "other",
                    "owner_user_id": obl.owner_user_id,
                    "escalation_user_id": obl.escalation_user_id,
                    "threshold_date": parse_date(obl.threshold_date),
                    "due_date": parse_date(obl.due_date),
                    "status": obl.status or "initiated",
                    "is_ai_generated": 1 if obl.is_ai_generated else 0,
                    "is_preset": 0,
                    "created_at": now,
                    "updated_at": now
                })
                created_count += 1
                
            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")
        
        db.commit()
        
        return {
            "success": True,
            "created": created_count,
            "errors": errors
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk creation failed: {str(e)}"
        )


@router.delete("/bulk-delete")
async def bulk_delete_obligations(
    obligation_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete multiple obligations at once"""
    try:
        deleted_count = 0
        
        for obl_id in obligation_ids:
            # Verify ownership
            check_query = """
                SELECT o.id FROM obligations o
                INNER JOIN contracts c ON o.contract_id = c.id
                WHERE o.id = :id AND c.company_id = :company_id
            """
            result = db.execute(text(check_query), {
                "id": obl_id,
                "company_id": current_user.company_id
            }).fetchone()
            
            if result:
                # Delete from all related tables first
                try:
                    db.execute(text("DELETE FROM obligation_updates WHERE obligation_id = :id"), {"id": obl_id})
                except: pass
                try:
                    db.execute(text("DELETE FROM obligation_tracking WHERE obligation_id = :id"), {"id": obl_id})
                except: pass
                try:
                    db.execute(text("DELETE FROM obligation_escalations WHERE obligation_id = :id"), {"id": obl_id})
                except: pass
                
                # Now delete the obligation
                db.execute(
                    text("DELETE FROM obligations WHERE id = :id"),
                    {"id": obl_id}
                )
                deleted_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "deleted": deleted_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk deletion failed: {str(e)}"
        )


# =====================================================
# 8. OBLIGATION TRACKING
# =====================================================

@router.post("/{obligation_id}/track")
async def add_tracking_entry(
    obligation_id: int,
    action_taken: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a tracking entry to an obligation"""
    try:
        # Verify obligation exists
        check_query = """
            SELECT o.id FROM obligations o
            INNER JOIN contracts c ON o.contract_id = c.id
            WHERE o.id = :id AND c.company_id = :company_id
        """
        result = db.execute(text(check_query), {
            "id": obligation_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Obligation not found"
            )
        
        insert_query = text("""
            INSERT INTO obligation_tracking (obligation_id, action_taken, action_by, notes, created_at)
            VALUES (:obligation_id, :action_taken, :action_by, :notes, :created_at)
        """)
        
        db.execute(insert_query, {
            "obligation_id": obligation_id,
            "action_taken": action_taken,
            "action_by": current_user.id,
            "notes": notes,
            "created_at": datetime.utcnow()
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": "Tracking entry added"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add tracking: {str(e)}"
        )


@router.get("/{obligation_id}/tracking")
async def get_tracking_history(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get tracking history for an obligation"""
    try:
        query = """
            SELECT 
                t.id,
                t.action_taken,
                t.notes,
                t.created_at,
                CONCAT(u.first_name, ' ', u.last_name) as action_by_name
            FROM obligation_tracking t
            LEFT JOIN users u ON t.action_by = u.id
            INNER JOIN obligations o ON t.obligation_id = o.id
            INNER JOIN contracts c ON o.contract_id = c.id
            WHERE t.obligation_id = :obligation_id AND c.company_id = :company_id
            ORDER BY t.created_at DESC
        """
        
        result = db.execute(text(query), {
            "obligation_id": obligation_id,
            "company_id": current_user.company_id
        })
        
        tracking = []
        for row in result:
            tracking.append({
                "id": row[0],
                "action_taken": row[1],
                "notes": row[2],
                "created_at": format_datetime(row[3]),
                "action_by_name": row[4]
            })
        
        return tracking
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracking: {str(e)}"
        )