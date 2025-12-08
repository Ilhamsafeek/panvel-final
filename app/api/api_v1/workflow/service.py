"""
Workflow Service - Complete Fixed Version
File: app/api/api_v1/workflow/service.py
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
import logging
import json

from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep

logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self, db: Session):
        self.db = db
    
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
            # Build base query
            base_filter = User.company_id == company_id
            
            # If no query string, get recent users
            if not query or query.strip() == '':
                users_query = self.db.query(User).filter(base_filter)
                
                # Add department filter if provided
                if department:
                    users_query = users_query.filter(User.department == department)
                
                users = users_query.limit(20).all()
            else:
                # Search with query
                search_filter = or_(
                    User.first_name.ilike(f"%{query}%"),
                    User.last_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%")
                )
                
                # Combine filters
                if department:
                    users = self.db.query(User).filter(
                        and_(
                            base_filter,
                            User.department == department,
                            search_filter
                        )
                    ).limit(10).all()
                else:
                    users = self.db.query(User).filter(
                        and_(
                            base_filter,
                            search_filter
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
    
    def create_workflow(
        self,
        company_id: int,
        name: str,
        steps_data: List[Dict[str, Any]],
        settings: Dict[str, Any],
        excluded_contract_types: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new workflow"""
        try:
            # Prepare workflow JSON - serialize to string for MySQL
            workflow_json_data = {
                "settings": settings,
                "excluded_types": excluded_contract_types or [],
                "steps": steps_data
            }
            workflow_json_str = json.dumps(workflow_json_data)
            
            # Create workflow
            workflow = Workflow(
                company_id=company_id,
                workflow_name=name,
                is_master=False,
                is_active=True,
                workflow_json=workflow_json_str,
                created_at=datetime.utcnow()
            )
            
            self.db.add(workflow)
            self.db.flush()
            
            # Create workflow steps
            for step_data in steps_data:
                step = WorkflowStep(
                    workflow_id=workflow.id,
                    step_number=step_data['step_order'],
                    step_name=step_data['role'],
                    step_type=step_data['role'].lower().replace(" ", "_"),
                    assignee_role=step_data.get('department'),
                    sla_hours=settings.get('auto_escalation_hours', 48),
                    is_mandatory=True,
                    created_at=datetime.utcnow()
                )
                self.db.add(step)
            
            self.db.commit()
            
            return {
                "id": workflow.id,
                "workflow_name": workflow.workflow_name,
                "is_active": workflow.is_active,
                "created_at": workflow.created_at.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating workflow: {e}", exc_info=True)
            return None
    
    def get_workflows(self, company_id: int) -> List[Dict[str, Any]]:
        """Get all workflows for a company"""
        try:
            workflows = self.db.query(Workflow).filter(
                Workflow.company_id == company_id
            ).order_by(Workflow.created_at.desc()).all()
            
            return [
                {
                    "id": wf.id,
                    "workflow_name": wf.workflow_name,
                    "description": wf.description,
                    "is_master": wf.is_master,
                    "is_active": wf.is_active,
                    "steps_count": self.db.query(WorkflowStep).filter(
                        WorkflowStep.workflow_id == wf.id
                    ).count(),
                    "created_at": wf.created_at.isoformat() if wf.created_at else None
                }
                for wf in workflows
            ]
        except Exception as e:
            logger.error(f"Error getting workflows: {e}")
            return []
    
    def get_workflow_details(self, workflow_id: int, company_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed workflow information"""
        try:
            workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.id == workflow_id,
                    Workflow.company_id == company_id
                )
            ).first()
            
            if not workflow:
                return None
            
            steps = self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id
            ).order_by(WorkflowStep.step_number).all()
            
            # Get settings from workflow_json if available - parse if string
            workflow_json = workflow.workflow_json or {}
            if isinstance(workflow_json, str):
                try:
                    workflow_json = json.loads(workflow_json)
                except:
                    workflow_json = {}
            
            settings = workflow_json.get('settings', {})
            
            return {
                "id": workflow.id,
                "workflow_name": workflow.workflow_name,
                "description": workflow.description,
                "is_master": workflow.is_master,
                "is_active": workflow.is_active,
                "settings": settings,
                "excluded_contract_types": workflow_json.get('excluded_types', []),
                "steps": [
                    {
                        "id": step.id,
                        "step_number": step.step_number,
                        "step_name": step.step_name,
                        "step_type": step.step_type,
                        "assignee_role": step.assignee_role,
                        "assignee_user_id": step.assignee_user_id,
                        "sla_hours": step.sla_hours,
                        "is_mandatory": step.is_mandatory
                    }
                    for step in steps
                ],
                "created_at": workflow.created_at.isoformat() if workflow.created_at else None
            }
        except Exception as e:
            logger.error(f"Error getting workflow details: {e}", exc_info=True)
            return None
    
    def update_workflow(
        self,
        workflow_id: int,
        company_id: int,
        name: str,
        steps_data: List[Dict[str, Any]],
        settings: Dict[str, Any],
        excluded_contract_types: List[str] = None
    ) -> bool:
        """Update an existing workflow"""
        try:
            workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.id == workflow_id,
                    Workflow.company_id == company_id
                )
            ).first()
            
            if not workflow:
                return False
            
            # Update workflow - serialize JSON to string for MySQL
            workflow_json_data = {
                "settings": settings,
                "excluded_types": excluded_contract_types or [],
                "steps": steps_data
            }
            workflow.workflow_name = name
            workflow.workflow_json = json.dumps(workflow_json_data)
            
            # Delete existing steps
            self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id
            ).delete()
            
            # Create new steps
            for step_data in steps_data:
                step = WorkflowStep(
                    workflow_id=workflow.id,
                    step_number=step_data['step_order'],
                    step_name=step_data['role'],
                    step_type=step_data['role'].lower().replace(" ", "_"),
                    assignee_role=step_data.get('department'),
                    sla_hours=settings.get('auto_escalation_hours', 48),
                    is_mandatory=True
                )
                self.db.add(step)
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating workflow: {e}", exc_info=True)
            return False
    
    def delete_workflow(self, workflow_id: int, company_id: int) -> bool:
        """Delete a workflow"""
        try:
            # Delete steps first
            self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow_id
            ).delete()
            
            # Delete workflow
            result = self.db.query(Workflow).filter(
                and_(
                    Workflow.id == workflow_id,
                    Workflow.company_id == company_id
                )
            ).delete()
            
            self.db.commit()
            return result > 0
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting workflow: {e}", exc_info=True)
            return False
    
    def get_master_workflow(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Get the master workflow for a company"""
        try:
            workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.company_id == company_id,
                    Workflow.is_master == True
                )
            ).first()
            
            if not workflow:
                return None
            
            steps = self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow.id
            ).order_by(WorkflowStep.step_number).all()
            
            # Get settings from workflow_json - parse if string
            workflow_json = workflow.workflow_json or {}
            if isinstance(workflow_json, str):
                try:
                    workflow_json = json.loads(workflow_json)
                except Exception as e:
                    logger.error(f"Error parsing workflow_json: {e}")
                    workflow_json = {}
            
            settings = workflow_json.get('settings', {})
            
            return {
                "id": workflow.id,
                "workflow_name": workflow.workflow_name,
                "description": workflow.description,
                "is_master": workflow.is_master,
                "is_active": workflow.is_active,
                "settings": settings,
                "excluded_contract_types": workflow_json.get('excluded_types', []),
                "steps": [
                    {
                        "id": step.id,
                        "step_number": step.step_number,
                        "step_name": step.step_name,
                        "step_type": step.step_type,
                        "assignee_role": step.assignee_role,
                        "assignee_user_id": step.assignee_user_id,
                        "sla_hours": step.sla_hours,
                        "is_mandatory": step.is_mandatory
                    }
                    for step in steps
                ],
                "created_at": workflow.created_at.isoformat() if workflow.created_at else None
            }
        except Exception as e:
            logger.error(f"Error getting master workflow: {e}", exc_info=True)
            return None
    
    def create_or_update_master_workflow(
        self,
        company_id: int,
        workflow_data: Any
    ) -> Optional[Dict[str, Any]]:
        """Create or update master workflow"""
        try:
            logger.info(f"Creating/updating master workflow for company {company_id}")
            logger.info(f"Workflow data type: {type(workflow_data)}")
            logger.info(f"Workflow data attributes: {dir(workflow_data)}")
            
            # Check if master workflow exists
            existing_workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.company_id == company_id,
                    Workflow.is_master == True
                )
            ).first()
            
            # Build settings from top-level attributes
            settings = {}
            if hasattr(workflow_data, 'auto_escalation'):
                settings['auto_escalation'] = workflow_data.auto_escalation
            if hasattr(workflow_data, 'escalation_hours'):
                settings['escalation_hours'] = workflow_data.escalation_hours
                
            # Handle old-style settings dict if it exists
            if hasattr(workflow_data, 'settings') and workflow_data.settings:
                settings.update(workflow_data.settings)
                
            logger.info(f"Settings built: {settings}")
            
            # Get workflow name
            workflow_name = workflow_data.workflow_name if hasattr(workflow_data, 'workflow_name') else workflow_data.name if hasattr(workflow_data, 'name') else "Master Workflow"
            
            # Get description
            description = workflow_data.description if hasattr(workflow_data, 'description') else None
            
            # Get excluded types
            excluded_types = []
            if hasattr(workflow_data, 'excluded_contract_types'):
                excluded_types = workflow_data.excluded_contract_types or []
            
            # Prepare workflow JSON - use actual attribute names from Pydantic model
            workflow_json_data = {
                "settings": settings,
                "excluded_types": excluded_types,
                "steps": [
                    {
                        "step_number": step.step_number if hasattr(step, 'step_number') else step.step_order if hasattr(step, 'step_order') else idx + 1,
                        "step_name": step.step_name if hasattr(step, 'step_name') else step.role if hasattr(step, 'role') else "Unknown",
                        "step_type": step.step_type if hasattr(step, 'step_type') else (step.role.lower().replace(" ", "_") if hasattr(step, 'role') else "unknown"),
                        "role": step.role if hasattr(step, 'role') else step.step_name if hasattr(step, 'step_name') else "Unknown",
                        "users": [
                            {
                                "id": u.id if hasattr(u, 'id') else None,
                                "name": u.name, 
                                "email": u.email,
                                "department": u.department if hasattr(u, 'department') else None
                            } 
                            for u in step.users
                        ] if step.users else [],
                        "department": step.department if hasattr(step, 'department') else None,
                        "sla_hours": step.sla_hours if hasattr(step, 'sla_hours') else settings.get('escalation_hours', 48)
                    }
                    for idx, step in enumerate(workflow_data.steps)
                ]
            }
            workflow_json_str = json.dumps(workflow_json_data)
            logger.info(f"Workflow JSON prepared: {len(workflow_json_str)} chars")
            
            # Get escalation hours from settings
            escalation_hours = settings.get('escalation_hours', 48)
            
            if existing_workflow:
                logger.info(f"Updating existing workflow ID {existing_workflow.id}")
                # Update existing workflow
                existing_workflow.workflow_name = workflow_name
                existing_workflow.description = description
                existing_workflow.workflow_json = workflow_json_str
                existing_workflow.updated_at = datetime.utcnow()
                
                # Delete existing steps
                self.db.query(WorkflowStep).filter(
                    WorkflowStep.workflow_id == existing_workflow.id
                ).delete()
                
                workflow = existing_workflow
            else:
                logger.info("Creating new master workflow")
                # Create new workflow
                workflow = Workflow(
                    company_id=company_id,
                    workflow_name=workflow_name,
                    description=description,
                    is_master=True,
                    is_active=True,
                    workflow_json=workflow_json_str,
                    created_at=datetime.utcnow()
                )
                self.db.add(workflow)
                self.db.flush()
                logger.info(f"New workflow created with ID {workflow.id}")
            
            # Create new steps - use actual Pydantic model attributes
            logger.info(f"Creating {len(workflow_data.steps)} workflow steps")
            for idx, step_data in enumerate(workflow_data.steps):
                # Get step number - try multiple attribute names
                step_number = step_data.step_number if hasattr(step_data, 'step_number') else step_data.step_order if hasattr(step_data, 'step_order') else idx + 1
                
                # Get step name - try multiple attribute names
                step_name = step_data.step_name if hasattr(step_data, 'step_name') else step_data.role if hasattr(step_data, 'role') else f"Step {idx + 1}"
                
                # Get step type
                step_type = step_data.step_type if hasattr(step_data, 'step_type') else step_name.lower().replace(" ", "_")
                
                # Get assignee role (department)
                assignee_role = step_data.department if hasattr(step_data, 'department') else step_data.assignee_role if hasattr(step_data, 'assignee_role') else None
                
                step = WorkflowStep(
                    workflow_id=workflow.id,
                    step_number=step_number,
                    step_name=step_name,
                    step_type=step_type,
                    assignee_role=assignee_role,
                    sla_hours=escalation_hours,
                    is_mandatory=True,
                    created_at=datetime.utcnow()
                )
                self.db.add(step)
                logger.info(f"Step {idx+1} created: {step.step_name} (step_number={step.step_number})")
            
            self.db.commit()
            logger.info("✅ Master workflow saved successfully")
            
            # Return the created/updated workflow
            result = self.get_master_workflow(company_id)
            logger.info(f"Returning workflow with {len(result['steps']) if result else 0} steps")
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating/updating master workflow: {e}", exc_info=True)
            logger.error(f"Workflow data: {workflow_data if 'workflow_data' in locals() else 'N/A'}")
            return None
    
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
            
            # Delete steps first
            self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow.id
            ).delete()
            
            # Delete workflow
            self.db.delete(workflow)
            self.db.commit()
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting master workflow: {e}", exc_info=True)
            return False