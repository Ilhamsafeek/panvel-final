# =====================================================
# FILE: app/api/api_v1/contracts/activity_logs.py
# Simple Activity Logs for Contract Dashboard
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/activity/{contract_id}")
async def get_contract_activity_logs(
    contract_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get simple activity logs for a contract - who did what and when
    """
    try:
        logger.info(f"📊 Fetching activity logs for contract {contract_id}")
        
        # Get activity logs with user details
        query = text("""
            SELECT 
                al.id,
                al.action_type,
                al.action_details,
                al.created_at,
                al.ip_address,
                u.id as user_id,
                CONCAT(u.first_name, ' ', u.last_name) as user_name,
                u.email as user_email
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.contract_id = :contract_id
            ORDER BY al.created_at DESC
            LIMIT :limit
        """)
        
        result = db.execute(query, {
            "contract_id": contract_id,
            "limit": limit
        })
        
        activities = []
        for row in result:
            # Parse action_details if it's a JSON string
            action_details = {}
            if row.action_details:
                try:
                    if isinstance(row.action_details, str):
                        action_details = json.loads(row.action_details)
                    else:
                        action_details = row.action_details
                except:
                    action_details = {"raw": str(row.action_details)}
            
            # Format action description
            action_desc = get_action_description(row.action_type, action_details)
            
            activities.append({
                "id": row.id,
                "action_type": row.action_type,
                "action_description": action_desc,
                "user_name": row.user_name or "System",
                "user_email": row.user_email or "system@calim360.com",
                "timestamp": row.created_at.isoformat() + 'Z' if row.created_at else None,  # 🔥 ADD 'Z'
                "ip_address": row.ip_address,
                "details": action_details
            })
        
        # Get statistics
        stats_query = text("""
            SELECT 
                COUNT(*) as total_activities,
                MAX(created_at) as last_activity
            FROM audit_logs
            WHERE contract_id = :contract_id
        """)
        
        stats_result = db.execute(stats_query, {"contract_id": contract_id}).fetchone()
        
        return {
            "success": True,
            "contract_id": contract_id,
            "activities": activities,
            "statistics": {
                "total_activities": stats_result.total_activities or 0,
                "last_activity_time": stats_result.last_activity.isoformat() if stats_result.last_activity else None
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching activity logs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching activity logs: {str(e)}"
        )


def get_action_description(action_type: str, details: dict) -> str:
    """
    Convert action type to human-readable description
    """
    descriptions = {
        "contract_created": "Created the contract",
        "contract_updated": "Updated contract details",
        "contract_deleted": "Deleted the contract",
        "contract_signed": "Signed the contract",
        "contract_submitted": "Submitted for review",
        "contract_approved": "Approved the contract",
        "contract_rejected": "Rejected the contract",
        "obligation_created": "Created new obligation",
        "obligation_updated": "Updated obligation",
        "obligation_completed": "Completed obligation",
        "document_uploaded": "Uploaded document",
        "document_downloaded": "Downloaded document",
        "comment_added": "Added comment",
        "workflow_started": "Started workflow",
        "workflow_completed": "Completed workflow step",
        "clause_added": "Added contract clause",
        "clause_updated": "Updated contract clause",
        "version_created": "Created new version",
        "signature_requested": "Requested signature",
        "negotiation_started": "Started negotiation",
        "ai_generation": "Generated content using AI",
        "blockchain_storage": "Stored on blockchain"
    }
    
    # Get description or default
    description = descriptions.get(action_type, action_type.replace('_', ' ').title())
    
    # Add specific details if available
    if details.get("entity_type"):
        description += f" ({details['entity_type']})"
    
    return description