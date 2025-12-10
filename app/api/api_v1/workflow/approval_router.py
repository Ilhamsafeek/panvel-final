from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ApprovalRequest(BaseModel):
    contract_id: int
    action: str  # 'approve' or 'reject'
    comments: Optional[str] = None

@router.post("/approve-reject")
async def approve_reject_workflow(
    request: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Handle workflow approval or rejection.
    - Approval: Move to next step, or complete if last step
    - Rejection: Just save comment, workflow stays at same step
    """
    try:
        # Get user ID from User object
        user_id = current_user.id
        
        # Get workflow instance for this contract
        workflow_query = text("""
            SELECT wi.id, wi.current_step, wi.workflow_id
            FROM workflow_instances wi
            WHERE wi.contract_id = :contract_id
            AND wi.status IN ('active', 'in_progress','pending')
            LIMIT 1
        """)
        workflow = db.execute(workflow_query, {"contract_id": request.contract_id}).first()
        db.commit()
        
        
        if not workflow:
            raise HTTPException(status_code=404, detail="No active workflow found for this contract")
        
        if request.action == "approve":
            # Get total steps in this workflow
            total_steps_query = text("""
                SELECT COUNT(DISTINCT step_number) as total
                FROM workflow_steps
                WHERE workflow_id = :workflow_id
            """)
            total_result = db.execute(total_steps_query, {"workflow_id": workflow.workflow_id}).first()
            total_steps = total_result.total if total_result else 0
            
            # Check if this is the last step
            if workflow.current_step >= total_steps:
                # Complete the workflow
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET status = 'completed',
                        current_step = 1,
                        completed_at = NOW()
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {"workflow_id": workflow.id})
                
                
                message = "Workflow completed successfully"
            else:
                # Move to next step
                next_step = workflow.current_step + 1
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET current_step = :next_step
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": next_step,
                    "workflow_id": workflow.id
                })
                
                message = f"Approved and Moved to step {next_step}"
            
            # Save approval record (optional - you can remove this if not needed)
            if request.comments:
                save_comment = text("""
                    INSERT INTO approval_requests 
                    (workflow_stage_id, contract_id, approver_id, action, comments, responded_at)
                    VALUES (NULL, :contract_id, :user_id, 'approve', :comments, NOW())
                """)
                db.execute(save_comment, {
                    "contract_id": request.contract_id,
                    "user_id": user_id,
                    "comments": request.comments
                })
            
            db.commit()
            return {"success": True, "message": message}
            
        elif request.action == "reject":
            # Just save the rejection comment, nothing else changes
            save_rejection = text("""
                INSERT INTO approval_requests 
                (workflow_stage_id, contract_id, approver_id, action, comments, responded_at)
                VALUES (NULL, :contract_id, :user_id, 'reject', :comments, NOW())
            """)
            db.execute(save_rejection, {
                "contract_id": request.contract_id,
                "user_id": user_id,
                "comments": request.comments or "Rejected"
            })
            
            db.commit()
            return {"success": True, "message": "Rejection comment saved"}
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error in approve/reject: {e}")
        raise HTTPException(status_code=500, detail=str(e))