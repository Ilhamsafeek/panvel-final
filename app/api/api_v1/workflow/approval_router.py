from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
import logging
import json
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)

class ApprovalRequest(BaseModel):
    contract_id: int
    request_type: str
    action: str  # 'approve' or 'reject'
    comments: Optional[str] = None


class NegotiationInitiationRequest(BaseModel):
    contract_id: int
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
        logger.info("="*80)
        logger.info(f"🔄 WORKFLOW APPROVAL/REJECTION REQUEST STARTED")
        logger.info("="*80)
        logger.info(f"📋 Request Details: {request.dict()}")
        logger.info(f"👤 User: {current_user.first_name} {current_user.last_name} (ID: {current_user.id})")
        logger.info(f"🏢 Company ID: {current_user.company_id}")
        logger.info(f"📄 Contract ID: {request.contract_id}")
        logger.info(f"⚡ Action: {request.action.upper()}")
        logger.info(f"📝 Request Type: {request.request_type}")
        logger.info(f" Comments: {request.comments or 'No comments provided'}")
        
        # Get user ID and company ID from User object
        user_id = current_user.id
        company_id = current_user.company_id
        
        # Get workflow instance FILTERED BY COMPANY
        logger.info(f"🔍 Searching for active workflow instance...")
        workflow_query = text("""
            SELECT wi.id, wi.current_step, wi.workflow_id, w.is_master
            FROM workflow_instances wi
            INNER JOIN workflows w ON wi.workflow_id = w.id
            WHERE wi.contract_id = :contract_id
            AND w.company_id = :company_id
            AND w.is_active = 1
            AND wi.status IN ('active', 'in_progress', 'pending')
            ORDER BY w.is_master ASC, w.id DESC
            LIMIT 1
        """)
        workflow = db.execute(workflow_query, {
            "contract_id": request.contract_id,
            "company_id": company_id
        }).first()
        
        if not workflow:
            logger.error(f"❌ No active workflow found for contract {request.contract_id} in company {company_id}")
            raise HTTPException(status_code=404, detail="No active workflow found for this contract in your company")
        
        logger.info(f" Workflow found:")
        logger.info(f"   - Workflow Instance ID: {workflow.id}")
        logger.info(f"   - Workflow ID: {workflow.workflow_id}")
        logger.info(f"   - Current Step: {workflow.current_step}")
        logger.info(f"   - Is Master Workflow: {workflow.is_master}")
        
        # =====================================================
        # APPROVAL FLOW
        # =====================================================
        if request.action == "approve":
            logger.info("="*80)
            logger.info(" PROCESSING APPROVAL")
            logger.info("="*80)
            
            # Get total steps in this workflow
            logger.info(f"🔍 Fetching total steps in workflow {workflow.workflow_id}...")
            total_steps_query = text("""
                SELECT COUNT(DISTINCT step_number) as total
                FROM workflow_steps
                WHERE workflow_id = :workflow_id
                AND step_type <> 'e_sign_authority'
            """)
            total_result = db.execute(total_steps_query, {"workflow_id": workflow.workflow_id}).first()
            total_steps = total_result.total if total_result else 0
            
            logger.info(f"📊 Workflow has {total_steps} total steps")
            logger.info(f"📍 Currently at step {workflow.current_step} of {total_steps}")
            
            # Check if this is the last step
            if workflow.current_step >= total_steps:
                logger.info("="*80)
                logger.info("🎉 THIS IS THE FINAL APPROVAL STEP")
                logger.info("="*80)
                
                # Complete the workflow
                logger.info(f"🔄 Updating workflow instance status to 'completed'...")
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
                logger.info(f" Workflow instance {workflow.id} marked as completed")

                logger.info(f"📋 Processing request type: {request.request_type}")
                
                # Update contract status based on request type
                if request.request_type == "internal_review":
                    logger.info("🔄 Internal Review completed - updating contract status...")
                    update_contract = text("""
                        UPDATE contracts
                        SET approval_status = 'review_completed',
                            status = 'review_completed',
                            workflow_status = 'completed'
                        WHERE id = :contract_id
                    """)
                    db.execute(update_contract, {"contract_id": request.contract_id})
                    logger.info(" Contract status updated: review_completed")
                    
                elif request.request_type == "counterparty_review":
                    logger.info("🔄 Counterparty Review completed - updating contract status...")
                    update_contract = text("""
                        UPDATE contracts
                        SET approval_status = 'counterparty_review_completed',
                            status = 'counterparty_review_completed'
                        WHERE id = :contract_id
                    """)
                    db.execute(update_contract, {"contract_id": request.contract_id})
                    logger.info(" Contract status updated: counterparty_review_completed")
                
                elif request.request_type == "approval":
                    logger.info("🔄 Final Approval completed - updating contract status...")
                    update_contract = text("""
                        UPDATE contracts
                        SET approval_status = 'approved',
                            status = 'approved'
                        WHERE id = :contract_id
                    """)
                    db.execute(update_contract, {"contract_id": request.contract_id})
                    logger.info(" Contract status updated: approved")
                else:
                    logger.warning(f"⚠️ Unknown request type: {request.request_type}")
                
                message = "Contract fully approved!"
                logger.info(f"🎉 {message}")
                
                # Create notification for contract owner
                logger.info("📧 Creating notification for contract owner...")
                contract_query = text("""
                    SELECT created_by, contract_title, contract_number
                    FROM contracts
                    WHERE id = :contract_id
                """)
                contract_info = db.execute(contract_query, {"contract_id": request.contract_id}).first()
                
                if contract_info and contract_info.created_by:
                    logger.info(f"👤 Sending notification to user {contract_info.created_by}")
                    logger.info(f"📄 Contract: {contract_info.contract_number} - {contract_info.contract_title}")
                    
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
                    logger.info(" Notification created successfully")
                else:
                    logger.warning("⚠️ Contract owner not found or invalid")
                
            else:
                logger.info("="*80)
                logger.info("➡️ MOVING TO NEXT WORKFLOW STEP")
                logger.info("="*80)
                
                # Move to next step
                next_step = workflow.current_step + 1
                logger.info(f"📍 Moving from step {workflow.current_step} to step {next_step}")
                
                # GET NEXT APPROVER'S NAME
                logger.info(f"🔍 Finding next approver for step {next_step}...")
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
                
                if next_approver:
                    logger.info(f" Next approver found:")
                    logger.info(f"   - Name: {next_approver.first_name} {next_approver.last_name}")
                    logger.info(f"   - Email: {next_approver.email}")
                    logger.info(f"   - User ID: {next_approver.id}")
                else:
                    logger.warning(f"⚠️ No approver found for step {next_step}")
                
                # Update workflow to next step
                logger.info(f"🔄 Updating workflow instance to step {next_step}...")
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET current_step = :next_step
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": next_step,
                    "workflow_id": workflow.id
                })
                logger.info(f" Workflow updated to step {next_step}")
                
                if next_approver:
                    approver_name = f"{next_approver.first_name} {next_approver.last_name}".strip()
                    if not approver_name:
                        approver_name = next_approver.email
                    message = f"Sent to {approver_name} for further approval"
                    logger.info(f" {message}")
                    
                    # Create notification for next approver
                    logger.info("📧 Creating notification for next approver...")
                    contract_query = text("""
                        SELECT contract_title, contract_number
                        FROM contracts
                        WHERE id = :contract_id
                    """)
                    contract_info = db.execute(contract_query, {"contract_id": request.contract_id}).first()
                    
                    logger.info(f"📄 Contract: {contract_info.contract_number} - {contract_info.contract_title}")
                    
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
                    logger.info(" Notification created for next approver")
                else:
                    message = f"Approved and moved to step {next_step}"
                    logger.info(f" {message}")
            
            # Log approval in audit_logs (this works correctly with INT IDs)
            logger.info("📝 Creating audit log entry for approval...")
            audit_log = text("""
                INSERT INTO audit_logs 
                (user_id, contract_id, action_type, action_details, created_at)
                VALUES (:user_id, :contract_id, 'approve', :action_details, NOW())
            """)
            audit_details = {
                "comment": request.comments or "Approved",
                "action": "workflow_approval",
                "workflow_step": workflow.current_step,
                "approver_name": f"{current_user.first_name} {current_user.last_name}",
                "timestamp": datetime.utcnow().isoformat()
            }
            db.execute(audit_log, {
                "user_id": user_id,
                "contract_id": request.contract_id,
                "action_details": json.dumps(audit_details)
            })
            logger.info(f" Audit log created: {audit_details}")
            
            logger.info("💾 Committing transaction...")
            db.commit()
            logger.info(" Transaction committed successfully")
            
            logger.info("="*80)
            logger.info(f" APPROVAL PROCESSED SUCCESSFULLY")
            logger.info(f"📨 Response: {message}")
            logger.info("="*80)
            
            return {"success": True, "message": message}
            
        # =====================================================
        # REJECTION FLOW
        # =====================================================
        elif request.action == "reject":
            logger.info("="*80)
            logger.info("❌ PROCESSING REJECTION")
            logger.info("="*80)
            
            # Log rejection in audit_logs (this works correctly with INT IDs)
            logger.info("📝 Creating audit log entry for rejection...")
            audit_log = text("""
                INSERT INTO audit_logs 
                (user_id, contract_id, action_type, action_details, created_at)
                VALUES (:user_id, :contract_id, 'reject', :action_details, NOW())
            """)
            audit_details = {
                "comment": request.comments or "Rejected",
                "action": "workflow_rejection",
                "workflow_step": workflow.current_step,
                "rejector_name": f"{current_user.first_name} {current_user.last_name}",
                "timestamp": datetime.utcnow().isoformat()
            }
            db.execute(audit_log, {
                "user_id": user_id,
                "contract_id": request.contract_id,
                "action_details": json.dumps(audit_details)
            })
            logger.info(f" Audit log created: {audit_details}")

            # Handle rejection for both initiator and counterparty internal reviews
            if request.request_type == "internal_review":
                logger.info("🔄 Initiator Internal Review rejected - resetting contract to draft...")
                
                update_contract = text("""
                    UPDATE contracts
                    SET status = 'draft',
                        approval_status = 'initiator_team_rejected'
                    WHERE id = :contract_id
                """)    
                db.execute(update_contract, {"contract_id": request.contract_id})
                logger.info(" Contract status updated to 'draft' with approval_status 'initiator_team_rejected'")

                logger.info("🔄 Resetting workflow to step 1...")
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET status = 'active',
                        current_step = 1
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": workflow.current_step + 1,
                    "workflow_id": workflow.id
                })
                logger.info(" Workflow reset to step 1 with status 'active'")
                
            elif request.request_type == "counterparty_internal_review":
                logger.info("🔄 Counterparty Internal Review rejected - resetting contract to counterparty review...")
                
                update_contract = text("""
                    UPDATE contracts
                    SET status = 'counterparty_internal_review',
                        approval_status = 'counterparty_team_rejected',
                        workflow_status = 'pending'
                    WHERE id = :contract_id
                """)    
                db.execute(update_contract, {"contract_id": request.contract_id})
                logger.info(" Contract status updated to 'counterparty_internal_review' with approval_status 'counterparty_team_rejected'")
                logger.info(" Workflow status set to 'pending'")

                logger.info("🔄 Resetting counterparty workflow to step 1...")
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET status = 'pending',
                        current_step = 1
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": workflow.current_step + 1,
                    "workflow_id": workflow.id
                })
                logger.info(" Counterparty workflow reset to step 1 with status 'pending'")

            elif request.request_type == "approval":
                logger.info("🔄 Counterparty Internal Review rejected - resetting contract to counterparty review...")
                
                update_contract = text("""
                    UPDATE contracts
                    SET status = 'negotiation_completed',
                        approval_status = 'approval_team_rejected',
                        workflow_status = 'pending'
                    WHERE id = :contract_id
                """)    
                db.execute(update_contract, {"contract_id": request.contract_id})
                logger.info(" Contract status updated to 'approval' with approval_status 'approval_team_rejected'")
                logger.info(" Workflow status set to 'pending'")

                logger.info("🔄 Resetting approval workflow to step 1...")
                update_workflow = text("""
                    UPDATE workflow_instances
                    SET status = 'pending',
                        current_step = 1
                    WHERE id = :workflow_id
                """)
                db.execute(update_workflow, {
                    "next_step": workflow.current_step + 1,
                    "workflow_id": workflow.id
                })
                logger.info(" Approval workflow reset to step 1 with status 'pending'")

            else:
                logger.info(f"ℹ️ Request type '{request.request_type}' - no additional contract updates")
            
            # Note: We do NOT insert into approval_requests because it has broken foreign keys
            # The audit_logs table is the authoritative record
            logger.info("ℹ️ Skipping approval_requests table (broken schema)")
            
            logger.info("💾 Committing transaction...")
            db.commit()
            logger.info(" Transaction committed successfully")
            
            logger.info("="*80)
            logger.info(" REJECTION PROCESSED SUCCESSFULLY")
            logger.info("📨 Response: Rejection comment saved")
            logger.info("="*80)
            
            return {"success": True, "message": "Rejection comment saved"}
        
        else:
            logger.error(f"❌ Invalid action received: {request.action}")
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except HTTPException as he:
        logger.error(f"❌ HTTP Exception: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error("="*80)
        logger.error(f"❌ CRITICAL ERROR IN APPROVAL/REJECTION WORKFLOW")
        logger.error("="*80)
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")
        logger.error(f"Contract ID: {request.contract_id if 'request' in locals() else 'Unknown'}")
        logger.error(f"User ID: {user_id if 'user_id' in locals() else 'Unknown'}")
        logger.error(f"Action: {request.action if 'request' in locals() else 'Unknown'}")
        logger.error("="*80)
        logger.error("Full Traceback:", exc_info=True)
        logger.error("="*80)
        logger.info("🔄 Transaction rolled back")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initiate-negotiation")
async def initiate_negotiation(
    request: NegotiationInitiationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        company_id = current_user.company_id
        
        # Verify contract exists
        verify_contract = text("""
            SELECT id, contract_number, contract_title, approval_status 
            FROM contracts 
            WHERE id = :contract_id
        """)
        contract = db.execute(verify_contract, {
            "contract_id": request.contract_id
        }).fetchone()
        
        if not contract:
            raise HTTPException(
                status_code=404, 
                detail="Contract not found or access denied"
            )
        
        # Update contract status to negotiation
        update_contract = text("""
            UPDATE contracts
            SET approval_status = 'negotiation',
                status = 'negotiation',
                updated_at = NOW()
            WHERE id = :contract_id 
        """)
        db.execute(update_contract, {
            "contract_id": request.contract_id
        })
        
        # OPTIONAL: Create audit trail entry (only if table exists)
        try:
            audit_entry = text("""
                INSERT INTO audit_logs 
                (user_id, contract_id, action_type, action_details, created_at)
                VALUES (:user_id, :contract_id, 'negotiation_initiated', :details, NOW())
            """)
            db.execute(audit_entry, {
                "user_id": user_id,
                "contract_id": request.contract_id,
                "details": json.dumps({"action": "negotiation_initiated", "initiated_by": user_id})
            })
        except Exception as audit_error:
            logger.warning(f"⚠️ Audit trail logging failed: {str(audit_error)}")
            # Continue anyway
        
        # CRITICAL: Commit the transaction
        db.commit()
        
        logger.info(f" Negotiation initiated for contract {request.contract_id} by user {user_id}")
        
        # =====================================================
        # SEND EMAIL NOTIFICATIONS TO MASTER WORKFLOW USERS
        # =====================================================
        try:
            from app.core.email import send_email_smtp
            
            # Get current user details
            user_query = text("""
                SELECT CONCAT(first_name, ' ', last_name) as full_name, email
                FROM users
                WHERE id = :user_id
            """)
            current_user_data = db.execute(user_query, {"user_id": user_id}).fetchone()
            
            # Get master workflow for this company
            workflow_query = text("""
                SELECT id, workflow_name
                FROM workflows
                WHERE company_id = :company_id
                AND is_master = 1
                AND is_active = 1
                LIMIT 1
            """)
            workflow = db.execute(workflow_query, {"company_id": company_id}).fetchone()
            
            if workflow:
                # Get all users from master workflow
                users_query = text("""
                    SELECT DISTINCT
                        u.id as user_id,
                        CONCAT(u.first_name, ' ', u.last_name) as full_name,
                        u.email,
                        u.user_role
                    FROM workflow_steps ws
                    INNER JOIN users u ON ws.assignee_user_id = u.id
                    WHERE ws.workflow_id = :workflow_id
                    AND u.company_id = :company_id
                    AND ws.assignee_user_id IS NOT NULL
                    AND u.is_active = 1
                    AND u.email IS NOT NULL
                """)
                workflow_users = db.execute(users_query, {
                    "workflow_id": workflow.id,
                    "company_id": company_id
                }).fetchall()
                
                # Contract URL
                contract_url = f"https://calim360.com/contract/edit/{request.contract_id}?action=view"
                
                email_count = 0
                for user in workflow_users:
                    # Don't send email to the user who initiated
                    if user.user_id == user_id:
                        continue
                    
                    email_subject = f"Internal Team Negotiation Started - {contract.contract_number}"
                    
                    email_body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                            <div style="background: linear-gradient(135deg, #2762cb 0%, #73B4E0 100%); padding: 20px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px;">
                                <h2 style="color: white; margin: 0;"> Internal Team Negotiation Started</h2>
                            </div>
                            
                            <p>Hi <strong>{user.full_name}</strong>,</p>
                            
                            <p><strong>{current_user_data.full_name}</strong> has initiated an internal team negotiation for contract review.</p>
                            
                            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                                <h3 style="margin-top: 0; color: #2762cb;">Contract Details:</h3>
                                <p style="margin: 5px 0;"><strong>Contract Number:</strong> {contract.contract_number}</p>
                                <p style="margin: 5px 0;"><strong>Contract Title:</strong> {contract.contract_title}</p>
                                <p style="margin: 5px 0;"><strong>Status:</strong> <span style="color: #ff9800; font-weight: bold;">Negotiation</span></p>
                            </div>
                            
                            <p>As a member of the master workflow team, your input and participation in this negotiation is requested.</p>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{contract_url}" 
                                   style="background: linear-gradient(135deg, #2762cb 0%, #73B4E0 100%); 
                                          color: white; 
                                          padding: 12px 30px; 
                                          text-decoration: none; 
                                          border-radius: 6px; 
                                          font-weight: bold;
                                          display: inline-block;">
                                    View Contract & Join Negotiation
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
                    
                    # Send email using existing service
                    try:
                        send_email_smtp(
                            to_email=user.email,
                            subject=email_subject,
                            html_body=email_body
                        )
                        email_count += 1
                        logger.info(f"✉️ Notification email sent to {user.email} ({user.full_name})")
                    except Exception as email_error:
                        logger.error(f"❌ Failed to send email to {user.email}: {str(email_error)}")
                        continue
                
                if email_count > 0:
                    logger.info(f"📧 Successfully sent {email_count} negotiation notification emails")
                else:
                    logger.warning("⚠️ No emails were sent (all users may have been the initiator)")
            else:
                logger.warning("⚠️ No master workflow found, skipping email notifications")
                
        except Exception as email_exception:
            logger.error(f"❌ Error in email notification process: {str(email_exception)}")
            # Don't fail the request if email service fails
            pass
        
        return {
            "success": True, 
            "message": "Negotiation Initiated Successfully! Team members have been notified.",
            "contract_id": request.contract_id
        }
        
    except HTTPException as he:
        logger.error(f"❌ HTTP Exception: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error("="*80)
        logger.error(f"❌ CRITICAL ERROR IN NEGOTIATION INITIATION")
        logger.error("="*80)
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")
        logger.error(f"Contract ID: {request.contract_id}")
        logger.error(f"User ID: {user_id}")
        logger.error(f"Company ID: {company_id}")
        logger.error("="*80)
        logger.error("Full Traceback:", exc_info=True)
        logger.error("="*80)
        logger.info("🔄 Transaction rolled back")
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
        
        logger.info(f" User {current_user.email} (Company {user_company_id}) accessed workflow history for contract {contract_id}")
        
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
        logger.error(f" Error fetching workflow history for contract {contract_id} by user {current_user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

