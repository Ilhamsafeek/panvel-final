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
        # Get user ID and company ID from User object
        user_id = current_user.id
        company_id = current_user.company_id
        
        # 🔥 Get workflow instance FILTERED BY COMPANY (join through workflows table)
        workflow_query = text("""
            SELECT wi.id, wi.current_step, wi.workflow_id
            FROM workflow_instances wi
            INNER JOIN workflows w ON wi.workflow_id = w.id
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :company_id
            AND wi.status IN ('active', 'in_progress','pending')
            LIMIT 1
        """)
        workflow = db.execute(workflow_query, {
            "contract_id": request.contract_id,
            "company_id": company_id
        }).first()
        db.commit()
        
        if not workflow:
            raise HTTPException(status_code=404, detail="No active workflow found for this contract in your company")
        
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
                
                # 🔥 CHECK IF CONTRACT BELONGS TO CURRENT USER'S COMPANY
                check_contract_company = text("""
                    SELECT company_id, status FROM contracts WHERE id = :contract_id
                """)
                contract_result = db.execute(check_contract_company, {
                    "contract_id": request.contract_id
                }).first()
                
                if contract_result and contract_result.company_id == company_id:
                    # Contract belongs to user's company → 'review_completed'
                    if contract_result.status == 'approval':
                        new_status = 'approved'
                    else: 
                        new_status = 'review_completed'
                    
                    message = "Workflow completed successfully"

                else:
                    # Contract belongs to counterparty → 'negotiation'
                    new_status = 'negotiation'
                    message = "Workflow completed - Contract moved to negotiation stage"
                
                # 🔥 UPDATE CONTRACT STATUS based on ownership
                update_contract_status = text("""
                    UPDATE contracts
                    SET status = :new_status,
                        updated_at = NOW()
                    WHERE id = :contract_id
                """)
                db.execute(update_contract_status, {
                    "contract_id": request.contract_id,
                    "new_status": new_status
                })
                
            else:
                # Move to next step
                next_step = workflow.current_step + 1
                
                # 🔥 GET NEXT APPROVER'S NAME (from same company)
                next_approver_query = text("""
                    SELECT u.first_name, u.last_name, u.email
                    FROM workflow_steps ws
                    INNER JOIN users u ON ws.assignee_user_id = u.id
                    WHERE ws.workflow_id = :workflow_id
                    AND ws.step_number = :next_step
                    AND u.company_id = :company_id
                    LIMIT 1
                """)
                next_approver = db.execute(next_approver_query, {
                    "workflow_id": workflow.workflow_id,
                    "next_step": next_step,
                    "company_id": company_id
                }).first()
                
                # Update workflow to next step
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET current_step = :next_step
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": next_step,
                    "workflow_id": workflow.id
                })
                
                # 🔥 CREATE MESSAGE WITH USER'S NAME
                if next_approver:
                    approver_name = f"{next_approver.first_name} {next_approver.last_name}".strip()
                    if not approver_name:  # If no name, use email
                        approver_name = next_approver.email
                    message = f"Sent to {approver_name} for further approval"
                else:
                    # Fallback if no user found
                    message = f"Approved and moved to step {next_step}"
            
            # Save approval record
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