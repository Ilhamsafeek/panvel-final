from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
import logging
import json


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
    
    NOTE: approval_requests table has broken schema (CHAR(36) FK to INT columns)
    so we only log to audit_logs which works correctly
    """
    try:
        logger.info(f"Received approval request: {request.dict()}")
        
        # Get user ID and company ID from User object
        user_id = current_user.id
        company_id = current_user.company_id
        
        # Get workflow instance FILTERED BY COMPANY
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
                        current_step = :next_step
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": workflow.current_step + 1,
                    "workflow_id": workflow.id
                })
                
                # Update contract status to approved
                update_contract = text("""
                    UPDATE contracts
                    SET approval_status = 'approved',
                        workflow_status = 'completed'
                    WHERE id = :contract_id
                """)
                db.execute(update_contract, {"contract_id": request.contract_id})
                
                message = "Contract fully approved!"
                
                # Create notification for contract owner
                contract_query = text("""
                    SELECT created_by, contract_title, contract_number
                    FROM contracts
                    WHERE id = :contract_id
                """)
                contract_info = db.execute(contract_query, {"contract_id": request.contract_id}).first()
                
                if contract_info and contract_info.created_by:
                    notification_query = text("""
                        INSERT INTO notifications 
                        (user_id, title, message, notification_type, is_read, created_at)
                        VALUES 
                        (:user_id, :title, :message, 'workflow', 0, NOW())
                    """)
                    db.execute(notification_query, {
                        "user_id": contract_info.created_by,
                        "title": "Contract Approved",
                        "message": f"Contract {contract_info.contract_number} - {contract_info.contract_title} has been fully approved."
                    })
                
            else:
                # Move to next step
                next_step = workflow.current_step + 1
                
                # GET NEXT APPROVER'S NAME
                next_approver_query = text("""
                    SELECT u.first_name, u.last_name, u.email, u.id
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
                
                if next_approver:
                    approver_name = f"{next_approver.first_name} {next_approver.last_name}".strip()
                    if not approver_name:
                        approver_name = next_approver.email
                    message = f"Sent to {approver_name} for further approval"
                    
                    # Create notification for next approver
                    contract_query = text("""
                        SELECT contract_title, contract_number
                        FROM contracts
                        WHERE id = :contract_id
                    """)
                    contract_info = db.execute(contract_query, {"contract_id": request.contract_id}).first()
                    
                    notification_query = text("""
                        INSERT INTO notifications 
                        (user_id, title, message, notification_type, is_read, created_at)
                        VALUES 
                        (:user_id, :title, :message, 'workflow', 0, NOW())
                    """)
                    db.execute(notification_query, {
                        "user_id": next_approver.id,
                        "title": "Contract Requires Your Approval",
                        "message": f"Contract {contract_info.contract_number} - {contract_info.contract_title} is waiting for your approval."
                    })
                else:
                    message = f"Approved and moved to step {next_step}"
            
            # Log approval in audit_logs (this works correctly with INT IDs)
            audit_log = text("""
                INSERT INTO audit_logs 
                (user_id, contract_id, action_type, action_details, created_at)
                VALUES (:user_id, :contract_id, 'approve', :action_details, NOW())
            """)
            db.execute(audit_log, {
                "user_id": user_id,
                "contract_id": request.contract_id,
                "action_details": json.dumps({
                    "comment": request.comments or "Approved",
                    "action": "workflow_approval",
                    "workflow_step": workflow.current_step
                })
            })
            
            db.commit()
            logger.info(f"✅ Approval processed for contract {request.contract_id}")
            return {"success": True, "message": message}
            
        elif request.action == "reject":
            # Log rejection in audit_logs (this works correctly with INT IDs)
            audit_log = text("""
                INSERT INTO audit_logs 
                (user_id, contract_id, action_type, action_details, created_at)
                VALUES (:user_id, :contract_id, 'reject', :action_details, NOW())
            """)
            db.execute(audit_log, {
                "user_id": user_id,
                "contract_id": request.contract_id,
                "action_details": json.dumps({
                    "comment": request.comments or "Rejected",
                    "action": "workflow_rejection",
                    "workflow_step": workflow.current_step
                })
            })
            
            # Note: We do NOT insert into approval_requests because it has broken foreign keys
            # The audit_logs table is the authoritative record
            
            db.commit()
            logger.info(f"✅ Rejection saved for contract {request.contract_id}")
            return {"success": True, "message": "Rejection comment saved"}
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error in approve/reject: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow-history/{contract_id}")
async def get_workflow_history(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get workflow history (approvals/rejections) for a contract from audit_logs
    WITH COMPANY-LEVEL ISOLATION - Users can only see history for their company's contracts
    """
    try:
        # Get user's company ID
        user_company_id = current_user.company_id
        
        # First, verify the contract belongs to the user's company
        contract_check = text("""
            SELECT id, company_id, contract_number, contract_title
            FROM contracts
            WHERE id = :contract_id
            AND company_id = :company_id
        """)
        
        contract = db.execute(contract_check, {
            "contract_id": contract_id,
            "company_id": user_company_id
        }).first()
        
        if not contract:
            raise HTTPException(
                status_code=403, 
                detail="Access denied: This contract does not belong to your company"
            )
        
        # Get workflow history from audit_logs - ONLY for users from the same company
        history_query = text("""
            SELECT 
                al.id,
                al.action_type,
                al.action_details,
                al.created_at,
                al.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.user_role,
                u.department
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            INNER JOIN contracts c ON al.contract_id = c.id
            WHERE al.contract_id = :contract_id
            AND c.company_id = :company_id
            AND u.company_id = :company_id
            AND al.action_type IN ('approve', 'reject', 'workflow_approval', 'workflow_rejection')
            ORDER BY al.created_at DESC
        """)
        
        results = db.execute(history_query, {
            "contract_id": contract_id,
            "company_id": user_company_id
        }).fetchall()
        
        logger.info(f"✅ User {current_user.email} (Company {user_company_id}) accessed workflow history for contract {contract_id}")
        
        history = []
        for row in results:
            # Parse JSON action_details
            try:
                action_details = json.loads(row.action_details) if row.action_details else {}
            except:
                action_details = {"comment": str(row.action_details)}
            
            # Build user display name
            user_name = f"{row.first_name or ''} {row.last_name or ''}".strip()
            if not user_name:
                user_name = row.email or "Unknown User"
            
            history.append({
                "id": row.id,
                "action": row.action_type,
                "comment": action_details.get("comment", "No comment provided"),
                "workflow_step": action_details.get("workflow_step"),
                "timestamp": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
                "user": {
                    "id": row.user_id,
                    "name": user_name,
                    "email": row.email,
                    "role": row.user_role,
                    "department": row.department
                }
            })
        
        return {
            "success": True,
            "contract": {
                "id": contract.id,
                "number": contract.contract_number,
                "title": contract.contract_title
            },
            "data": history,
            "total": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching workflow history for contract {contract_id} by user {current_user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

