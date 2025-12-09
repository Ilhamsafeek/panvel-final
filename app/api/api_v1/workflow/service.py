# =====================================================
# FILE: app/api/api_v1/workflow/service.py
# COMPLETE REWRITE - FIXED VERSION
# =====================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging
from sqlalchemy import or_, and_

from app.models.workflow import Workflow, WorkflowStep
from app.models.user import User

logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_master_workflow(self, company_id: int):
        """Get active master workflow with ALL details - FIXED"""
        try:
            # Get workflow
            workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.company_id == company_id,
                    Workflow.is_master == True,
                    Workflow.is_active == True
                )
            ).first()
            
            if not workflow:
                logger.info(f"No master workflow found for company {company_id}")
                return None
            
            logger.info(f"Found workflow ID {workflow.id}, workflow_json: {workflow.workflow_json}")
            
            # Get department mapping from workflow_json
            departments_map = {}
            if workflow.workflow_json:
                try:
                    if isinstance(workflow.workflow_json, str):
                        config = json.loads(workflow.workflow_json)
                    else:
                        config = workflow.workflow_json
                    departments_map = config.get('departments', {})
                    logger.info(f"Department mapping loaded: {departments_map}")
                except Exception as e:
                    logger.error(f"Error parsing workflow_json: {e}")
            
            # Get steps
            steps = self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow.id
            ).order_by(WorkflowStep.step_number, WorkflowStep.id).all()
            
            logger.info(f"Found {len(steps)} workflow step entries")
            
            workflow_dict = {
                "id": workflow.id,
                "workflow_name": workflow.workflow_name,
                "description": workflow.description,
                "is_master": workflow.is_master,
                "is_active": workflow.is_active,
                "created_at": workflow.created_at,
                "steps": []
            }
            
            # Process each step with user data
            for step in steps:
                # Get department - robust extraction
                dept = None
                if str(step.step_number) in departments_map:
                    dept = departments_map[str(step.step_number)]
                elif step.step_number in departments_map:
                    dept = departments_map[step.step_number]
                else:
                    dept = ''
                
                logger.info(f"Step {step.step_number}: role={step.assignee_role}, user_id={step.assignee_user_id}, dept='{dept}'")
                
                step_dict = {
                    "id": step.id,
                    "step_number": step.step_number,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "assignee_role": step.assignee_role,
                    "assignee_user_id": step.assignee_user_id,
                    "sla_hours": step.sla_hours,
                    "is_mandatory": step.is_mandatory,
                    "department": dept,  # This is now properly included
                    "user_name": None,
                    "user_email": None,
                    "assignee_user": None
                }
                
                # Load user if assigned
                if step.assignee_user_id:
                    user = self.db.query(User).filter(User.id == step.assignee_user_id).first()
                    if user:
                        user_name = f"{user.first_name} {user.last_name}"
                        step_dict["user_name"] = user_name
                        step_dict["user_email"] = user.email
                        step_dict["assignee_user"] = {
                            "id": user.id,
                            "name": user_name,
                            "email": user.email
                        }
                        logger.info(f"  -> User found: {user_name} ({user.email})")
                    else:
                        logger.warning(f"  -> User ID {step.assignee_user_id} NOT FOUND in database!")
                
                workflow_dict["steps"].append(step_dict)
            
            logger.info(f"Returning {len(workflow_dict['steps'])} steps to frontend")
            
            # Debug: Check final structure
            for i, step in enumerate(workflow_dict['steps']):
                logger.info(f"Final Step {i+1}: dept='{step.get('department')}'")
            
            return workflow_dict
            
        except Exception as e:
            logger.error(f"Error in get_master_workflow: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def create_or_update_master_workflow(
        self,
        company_id: int,
        workflow_data: Any
    ):
        """Create or update master workflow - FIXED VERSION"""
        try:
            logger.info(f"Creating workflow for company {company_id}")
            logger.info(f"Received {len(workflow_data.steps)} steps")
            
            # Deactivate existing master workflow
            existing = self.db.query(Workflow).filter(
                and_(
                    Workflow.company_id == company_id,
                    Workflow.is_master == True
                )
            ).all()
            
            for ex in existing:
                ex.is_active = False
                logger.info(f"Deactivated workflow ID {ex.id}")
            
            self.db.commit()
            
            # Build department mapping
            departments_map = {}
            for step_data in workflow_data.steps:
                if step_data.department:
                    departments_map[step_data.step_number] = step_data.department
                    logger.info(f"Department mapping: Step {step_data.step_number} -> {step_data.department}")
            
            logger.info(f"Final departments_map to save: {departments_map}")
            
            # Create new master workflow
            workflow = Workflow(
                company_id=company_id,
                workflow_name=workflow_data.workflow_name,
                description=workflow_data.description,
                workflow_type="master",
                is_master=True,
                is_active=True,
                workflow_json=json.dumps({
                    "auto_escalation": workflow_data.auto_escalation,
                    "escalation_hours": workflow_data.escalation_hours,
                    "departments": departments_map
                }),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db.add(workflow)
            self.db.flush()  # Get workflow ID
            logger.info(f"Created workflow ID {workflow.id}")
            logger.info(f"Saved workflow_json: {workflow.workflow_json}")
            
            # Create workflow steps - ONE ENTRY PER USER
            step_count = 0
            for step_data in workflow_data.steps:
                logger.info(f"Processing step {step_data.step_number}: {step_data.role}, dept={step_data.department}")
                logger.info(f"  Users in this step: {len(step_data.users)}")
                
                if step_data.users and len(step_data.users) > 0:
                    # Create separate WorkflowStep entry for each user
                    for user in step_data.users:
                        step = WorkflowStep(
                            workflow_id=workflow.id,
                            step_number=step_data.step_number,
                            step_name=step_data.step_name or step_data.role,
                            step_type=step_data.step_type or step_data.role,
                            assignee_role=step_data.role,
                            assignee_user_id=user.id,
                            sla_hours=step_data.sla_hours or 24,
                            is_mandatory=step_data.is_mandatory,
                            created_at=datetime.utcnow()
                        )
                        self.db.add(step)
                        step_count += 1
                        logger.info(f"  Added step entry for user ID {user.id} ({user.name})")
                else:
                    # Create step without user
                    step = WorkflowStep(
                        workflow_id=workflow.id,
                        step_number=step_data.step_number,
                        step_name=step_data.step_name or step_data.role,
                        step_type=step_data.step_type or step_data.role,
                        assignee_role=step_data.role,
                        assignee_user_id=None,
                        sla_hours=step_data.sla_hours or 24,
                        is_mandatory=step_data.is_mandatory,
                        created_at=datetime.utcnow()
                    )
                    self.db.add(step)
                    step_count += 1
                    logger.info(f"  Added step entry without user")
            
            self.db.commit()
            logger.info(f"Successfully saved {step_count} workflow step entries")
            
            # Return the created workflow
            return self.get_master_workflow(company_id)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating workflow: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def delete_master_workflow(self, company_id: int) -> bool:
        """Delete master workflow"""
        try:
            workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.company_id == company_id,
                    Workflow.is_master == True
                )
            ).first()
            
            if not workflow:
                return False
            
            # Delete steps
            self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow.id
            ).delete()
            
            # Delete workflow
            self.db.delete(workflow)
            self.db.commit()
            
            logger.info(f"Deleted workflow ID {workflow.id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting workflow: {e}")
            return False
    
    def get_available_roles(self) -> List[str]:
        """Get predefined workflow roles"""
        return [
            "Reviewer",
            "Approver", 
            "Legal Reviewer",
            "Finance Approver",
            "Director",
            "E-Sign Authority",
            "Counter-Party"
        ]
    
    def get_company_departments(self, company_id: int) -> List[Dict[str, Any]]:
        """Get company departments"""
        return [
            {"id": 1, "name": "Legal"},
            {"id": 2, "name": "Finance"},
            {"id": 3, "name": "Operations"},
            {"id": 4, "name": "Sales"},
            {"id": 5, "name": "HR"},
            {"id": 6, "name": "IT"},
            {"id": 7, "name": "Procurement"}
        ]

        
    def search_users(
        self,
        company_id: int,
        query: str,
        department: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search users by name or email, optionally filter by department"""
        try:
            # Base query
            base_query = self.db.query(User).filter(
                User.company_id == company_id,
                User.is_active == True
            )
            
            # Apply department filter if provided
            if department:
                base_query = base_query.filter(User.department == department)
            
            # Apply search query
            if not query or query.strip() == '':
                users = base_query.limit(20).all()
            else:
                users = base_query.filter(
                    or_(
                        User.first_name.ilike(f"%{query}%"),
                        User.last_name.ilike(f"%{query}%"),
                        User.email.ilike(f"%{query}%")
                    )
                ).limit(10).all()
            
            return [
                {
                    "id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "email": user.email,
                    "user_type": user.user_type,
                    "department": getattr(user, 'department', None)
                }
                for user in users
            ]
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []