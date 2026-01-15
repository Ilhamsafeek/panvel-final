"""
Dashboard API Router - FINAL FIX with Correct MySQL Schema
File: app/api/api_v1/dashboard/router.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
@router.get("/statistics")
async def get_dashboard_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard statistics with real-time data
    Includes contracts where company is either primary party or party B
    INCLUDES: My Pending Approvals (contracts awaiting current user's approval)
    INCLUDES: Project Statistics (active projects, project value, projects by status)
    """
    try:
        company_id = current_user.company_id
        user_id = current_user.id
        today = datetime.now()
        
        # Total Contracts - including party_b_id
        total_contracts_result = db.execute(
            text("""
                SELECT COUNT(*) as count FROM contracts 
                WHERE company_id = :company_id OR party_b_id = :company_id
            """),
            {"company_id": company_id}
        ).fetchone()
        total_contracts = total_contracts_result.count if total_contracts_result else 0
        
        # Active Contracts - including party_b_id
        active_contracts_result = db.execute(
            text("""
                SELECT COUNT(*) as count FROM contracts 
                WHERE (company_id = :company_id OR party_b_id = :company_id) 
                AND status = 'executed'
            """),
            {"company_id": company_id}
        ).fetchone()
        active_contracts = active_contracts_result.count if active_contracts_result else 0
        
        # Expiring Soon (within 30 days) - including party_b_id
        thirty_days_from_now = today + timedelta(days=30)
        expiring_soon_result = db.execute(
            text("""
                SELECT COUNT(*) as count FROM contracts 
                WHERE (company_id = :company_id OR party_b_id = :company_id)
                AND status = 'executed'
                AND end_date BETWEEN :today AND :end_date
            """),
            {
                "company_id": company_id,
                "today": today.date(),
                "end_date": thirty_days_from_now.date()
            }
        ).fetchone()
        expiring_soon = expiring_soon_result.count if expiring_soon_result else 0
        
        # Pending Approvals (Company-wide) - including party_b_id
        pending_approvals_result = db.execute(
            text("""
                SELECT COUNT(DISTINCT wi.id) as count 
                FROM workflow_instances wi
                JOIN contracts c ON wi.contract_id = c.id
                WHERE (c.company_id = :company_id OR c.party_b_id = :company_id)
                AND wi.status IN ('pending', 'in_progress', 'active')
            """),
            {"company_id": company_id}
        ).fetchone()
        pending_approvals = pending_approvals_result.count if pending_approvals_result else 0
        
        # 🆕 MY PENDING APPROVALS - Using same logic as is_my_workflow_turn
        # Counts contracts where current workflow step is assigned to current user
        my_pending_approvals_result = db.execute(
            text("""
                SELECT COUNT(*) as count
                FROM contracts
                WHERE action_person_id = :user_id
                AND (company_id = :company_id OR party_b_id = :company_id)
                AND status IN ('approval', 'signature', 'review','draft')
            """),
            {"company_id": company_id, "user_id": user_id}
        ).fetchone()
        my_pending_approvals = my_pending_approvals_result.count if my_pending_approvals_result else 0
        
        # Contracts by Status - including party_b_id
        status_breakdown_result = db.execute(
            text("""
                SELECT status, COUNT(*) as count 
                FROM contracts 
                WHERE company_id = :company_id OR party_b_id = :company_id
                GROUP BY status
            """),
            {"company_id": company_id}
        ).fetchall()
        
        status_breakdown = {row.status: row.count for row in status_breakdown_result}
        
        # Obligations Statistics - including party_b_id
        total_obligations_result = db.execute(
            text("""
                SELECT COUNT(o.id) as count
                FROM obligations o
                JOIN contracts c ON o.contract_id = c.id
                WHERE c.company_id = :company_id OR c.party_b_id = :company_id
            """),
            {"company_id": company_id}
        ).fetchone()
        total_obligations = total_obligations_result.count if total_obligations_result else 0
        
        overdue_obligations_result = db.execute(
            text("""
                SELECT COUNT(o.id) as count
                FROM obligations o
                JOIN contracts c ON o.contract_id = c.id
                WHERE (c.company_id = :company_id OR c.party_b_id = :company_id)
                AND o.status IN ('pending', 'in_progress')
                AND o.due_date < :today
            """),
            {"company_id": company_id, "today": today.date()}
        ).fetchone()
        overdue_obligations = overdue_obligations_result.count if overdue_obligations_result else 0
        
        upcoming_obligations_result = db.execute(
            text("""
                SELECT COUNT(o.id) as count
                FROM obligations o
                JOIN contracts c ON o.contract_id = c.id
                WHERE (c.company_id = :company_id OR c.party_b_id = :company_id)
                AND o.status IN ('pending', 'in_progress')
                AND o.due_date BETWEEN :today AND :end_date
            """),
            {
                "company_id": company_id,
                "today": today.date(),
                "end_date": thirty_days_from_now.date()
            }
        ).fetchone()
        upcoming_obligations = upcoming_obligations_result.count if upcoming_obligations_result else 0
        
        # Document Statistics - uploaded_documents has user_id not company_id
        total_documents_result = db.execute(
            text("""
                SELECT COUNT(DISTINCT ud.id) as count 
                FROM uploaded_documents ud
                JOIN users u ON ud.user_id = u.id
                WHERE u.company_id = :company_id
            """),
            {"company_id": company_id}
        ).fetchone()
        total_documents = total_documents_result.count if total_documents_result else 0
        
        # 🆕 PROJECT STATISTICS
        # Active Projects Count
        active_projects_result = db.execute(
            text("""
                SELECT COUNT(*) as count 
                FROM projects 
                WHERE company_id = :company_id 
                AND status = 'active'
            """),
            {"company_id": company_id}
        ).fetchone()
        active_projects = active_projects_result.count if active_projects_result else 0
        
        # Total Projects Count (all statuses)
        total_projects_result = db.execute(
            text("""
                SELECT COUNT(*) as count 
                FROM projects 
                WHERE company_id = :company_id
            """),
            {"company_id": company_id}
        ).fetchone()
        total_projects = total_projects_result.count if total_projects_result else 0
        
        # Total Project Value (Active Projects)
        total_project_value_result = db.execute(
            text("""
                SELECT COALESCE(SUM(project_value), 0) as total_value,
                       COALESCE(AVG(project_value), 0) as avg_value
                FROM projects 
                WHERE company_id = :company_id 
                AND status = 'active'
                AND project_value IS NOT NULL
            """),
            {"company_id": company_id}
        ).fetchone()
        total_project_value = total_project_value_result.total_value if total_project_value_result else 0
        avg_project_value = total_project_value_result.avg_value if total_project_value_result else 0
        
        # Projects by Status
        projects_by_status_result = db.execute(
            text("""
                SELECT status, COUNT(*) as count 
                FROM projects 
                WHERE company_id = :company_id
                GROUP BY status
            """),
            {"company_id": company_id}
        ).fetchall()
        projects_by_status = {row.status: row.count for row in projects_by_status_result}
        
        # Recent Projects (last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        recent_projects_result = db.execute(
            text("""
                SELECT COUNT(*) as count 
                FROM projects 
                WHERE company_id = :company_id
                AND created_at >= :thirty_days_ago
            """),
            {"company_id": company_id, "thirty_days_ago": thirty_days_ago}
        ).fetchone()
        recent_projects = recent_projects_result.count if recent_projects_result else 0
        
        # Projects by Type
        projects_by_type_result = db.execute(
            text("""
                SELECT project_type, COUNT(*) as count 
                FROM projects 
                WHERE company_id = :company_id
                AND project_type IS NOT NULL
                GROUP BY project_type
            """),
            {"company_id": company_id}
        ).fetchall()
        projects_by_type = {row.project_type: row.count for row in projects_by_type_result}
        
        # Recent Activity (last 7 days) - including party_b_id
        seven_days_ago = today - timedelta(days=7)
        recent_contracts_result = db.execute(
            text("""
                SELECT COUNT(*) as count FROM contracts 
                WHERE (company_id = :company_id OR party_b_id = :company_id)
                AND created_at >= :seven_days_ago
            """),
            {"company_id": company_id, "seven_days_ago": seven_days_ago}
        ).fetchone()
        recent_contracts = recent_contracts_result.count if recent_contracts_result else 0
        
        # Contract Value Statistics - including party_b_id
        contract_values_result = db.execute(
            text("""
                SELECT 
                    COALESCE(SUM(contract_value), 0) as total_value,
                    COALESCE(AVG(contract_value), 0) as avg_value,
                    COUNT(*) as count
                FROM contracts 
                WHERE (company_id = :company_id OR party_b_id = :company_id)
                AND contract_value IS NOT NULL
            """),
            {"company_id": company_id}
        ).fetchone()
        
        # Workflow Statistics - including party_b_id
        workflows_stats_result = db.execute(
            text("""
                SELECT wi.status, COUNT(*) as count 
                FROM workflow_instances wi
                JOIN contracts c ON wi.contract_id = c.id
                WHERE c.company_id = :company_id OR c.party_b_id = :company_id
                GROUP BY wi.status
            """),
            {"company_id": company_id}
        ).fetchall()
        
        workflow_breakdown = {row.status: row.count for row in workflows_stats_result}
        
        # Risk Assessment - risk_level column doesn't exist, skip for now
        high_risk_contracts = 0
        
        logger.info(f"📊 Dashboard Stats - User: {current_user.email}, Total Contracts: {total_contracts}, Active Projects: {active_projects}, My Pending Approvals: {my_pending_approvals}")
        
        return {
            "success": True,
            "data": {
                "overview": {
                    "total_contracts": total_contracts,
                    "active_contracts": active_contracts,
                    "expiring_soon": expiring_soon,
                    "pending_approvals": pending_approvals,
                    "my_pending_approvals": my_pending_approvals,
                    "recent_contracts": recent_contracts
                },
                "contracts": {
                    "by_status": status_breakdown,
                    "total_value": float(contract_values_result.total_value or 0),
                    "average_value": float(contract_values_result.avg_value or 0),
                    "high_risk": high_risk_contracts
                },
                "obligations": {
                    "total": total_obligations,
                    "overdue": overdue_obligations,
                    "upcoming": upcoming_obligations,
                    "completion_rate": round((total_obligations - overdue_obligations) / total_obligations * 100, 1) if total_obligations > 0 else 0
                },
                "workflows": {
                    "by_status": workflow_breakdown,
                    "pending": workflow_breakdown.get('pending', 0),
                    "in_progress": workflow_breakdown.get('in_progress', 0),
                    "completed": workflow_breakdown.get('completed', 0)
                },
                "documents": {
                    "total": total_documents
                },
                "projects": {
                    "total": total_projects,
                    "active": active_projects,
                    "total_value": float(total_project_value or 0),
                    "average_value": float(avg_project_value or 0),
                    "by_status": projects_by_status,
                    "by_type": projects_by_type,
                    "recent": recent_projects
                }
            }
        }
        
    except Exception as e:
        logger.error(f" Error fetching dashboard statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

        
        
@router.get("/expiring-contracts")
async def get_expiring_contracts(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of contracts expiring within specified days"""
    try:
        today = datetime.now()
        end_date = today + timedelta(days=days)
        
        # Use party_b_name from contracts table
        contracts_result = db.execute(
            text("""
                SELECT 
                    c.id, c.contract_number, c.contract_title,
                    COALESCE(c.party_b_name, 'N/A') as counterparty,
                    c.end_date, c.contract_value, c.status,
                    DATEDIFF(c.end_date, :today) as days_remaining
                FROM contracts c
                WHERE c.company_id = :company_id
                AND c.status = 'active'
                AND c.end_date BETWEEN :today AND :end_date
                ORDER BY c.end_date ASC
                LIMIT 10
            """),
            {
                "company_id": current_user.company_id,
                "today": today.date(),
                "end_date": end_date.date()
            }
        ).fetchall()
        
        return {
            "success": True,
            "data": [
                {
                    "id": c.id,
                    "contract_number": c.contract_number,
                    "title": c.contract_title,
                    "counterparty": c.counterparty,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "days_remaining": c.days_remaining if c.days_remaining else 0,
                    "contract_value": float(c.contract_value or 0),
                    "status": c.status
                }
                for c in contracts_result
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching expiring contracts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent activities from audit log"""
    try:
        # audit_logs actual columns: id, user_id, contract_id, action_type, action_details, ip_address, user_agent, created_at
        activities_result = db.execute(
            text("""
                SELECT 
                    al.id, 
                    COALESCE(al.action_type, 'activity') as action, 
                    COALESCE(al.action_details, al.action_type, 'Activity') as description, 
                    'contract' as entity_type, 
                    al.contract_id as entity_id, 
                    al.created_at,
                    CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, '')) as user_name
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                WHERE al.user_id IN (
                    SELECT id FROM users WHERE company_id = :company_id
                )
                ORDER BY al.created_at DESC
                LIMIT :limit
            """),
            {"company_id": current_user.company_id, "limit": limit}
        ).fetchall()
        
        return {
            "success": True,
            "data": [
                {
                    "id": a.id,
                    "action": a.action,
                    "description": a.description,
                    "user": a.user_name if a.user_name else "System",
                    "timestamp": a.created_at.isoformat() if a.created_at else None,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id
                }
                for a in activities_result
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        # Return empty data instead of error for better UX
        return {
            "success": True,
            "data": []
        }


@router.get("/obligations-due-soon")
async def get_obligations_due_soon(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get obligations due in the next specified days"""
    try:
        today = datetime.now()
        end_date = today + timedelta(days=days)
        
        # Use obligation_title and description columns, no completion_percentage exists
        obligations_result = db.execute(
            text("""
                SELECT 
                    o.id, 
                    COALESCE(o.obligation_title, o.description, o.obligation_type, 'Obligation') as title,
                    o.due_date, 
                    'medium' as priority,
                    o.status,
                    0 as completion_percentage, 
                    c.contract_number,
                    DATEDIFF(o.due_date, :today) as days_remaining
                FROM obligations o
                JOIN contracts c ON o.contract_id = c.id
                WHERE c.company_id = :company_id
                AND o.status IN ('pending', 'in_progress')
                AND o.due_date BETWEEN :today AND :end_date
                ORDER BY o.due_date ASC
                LIMIT 10
            """),
            {
                "company_id": current_user.company_id,
                "today": today.date(),
                "end_date": end_date.date()
            }
        ).fetchall()
        
        return {
            "success": True,
            "data": [
                {
                    "id": o.id,
                    "title": o.title,
                    "contract": o.contract_number,
                    "due_date": o.due_date.isoformat() if o.due_date else None,
                    "days_remaining": o.days_remaining if o.days_remaining else 0,
                    "priority": o.priority,
                    "status": o.status,
                    "completion_percentage": o.completion_percentage or 0
                }
                for o in obligations_result
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching obligations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contract-trends")
async def get_contract_trends(
    period: str = "month",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get contract creation trends over time"""
    try:
        if period == "month":
            days = 30
        elif period == "quarter":
            days = 90
        else:
            days = 365
            
        start_date = datetime.now() - timedelta(days=days)
        
        trends_result = db.execute(
            text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM contracts
                WHERE company_id = :company_id
                AND created_at >= :start_date
                GROUP BY DATE(created_at)
                ORDER BY date
            """),
            {"company_id": current_user.company_id, "start_date": start_date}
        ).fetchall()
        
        return {
            "success": True,
            "data": [
                {
                    "date": t.date.isoformat() if t.date else None,
                    "count": t.count
                }
                for t in trends_result
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching contract trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contract-types-distribution")
async def get_contract_types_distribution(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get distribution of contracts by type"""
    try:
        distribution_result = db.execute(
            text("""
                SELECT 
                    contract_type,
                    COUNT(*) as count
                FROM contracts
                WHERE company_id = :company_id
                GROUP BY contract_type
            """),
            {"company_id": current_user.company_id}
        ).fetchall()
        
        return {
            "success": True,
            "data": [
                {
                    "type": t.contract_type if t.contract_type else "Unknown",
                    "count": t.count
                }
                for t in distribution_result
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching contract types: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backward compatibility
@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Legacy stats endpoint - redirects to /statistics"""
    return await get_dashboard_statistics(current_user, db)



@router.get("/pending-actions")
async def get_pending_actions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all contracts where action_person_id = current user ID
    These are contracts requiring the current user's action
    """
    try:
        logger.info("="*80)
        logger.info(f"📋 FETCHING PENDING ACTIONS")
        logger.info("="*80)
        logger.info(f"👤 User ID: {current_user.id}")
        logger.info(f"🏢 Company ID: {current_user.company_id}")
        
        # Query contracts where action_person_id = current user
        query = text("""
            SELECT 
                c.id,
                c.contract_number,
                c.contract_title,
                c.status,
                c.created_at,
                c.updated_at,
                c.contract_type,
                c.contract_value,
                c.currency,
                c.action_person_id,
                CASE 
                    WHEN c.status = 'draft' THEN 'draft'
                    WHEN c.status = 'approval' THEN 'approval'
                    WHEN c.status = 'signature' THEN 'signature'
                    WHEN c.status = 'review' THEN 'review'
                    ELSE 'review'
                END as action_type,
                CASE
                    WHEN c.status = 'draft' THEN 'This contract requires your drafting'
                    WHEN c.status = 'approval' THEN 'This contract requires your approval'
                    WHEN c.status = 'signature' THEN 'This contract requires your signature'
                    WHEN c.status = 'review' THEN 'This contract requires your review'
                    ELSE 'Action required on this contract'
                END as description
            FROM contracts c
            WHERE c.action_person_id = :user_id
            AND c.company_id = :company_id
            AND c.status IN ('approval', 'signature', 'review','draft')
            ORDER BY c.updated_at DESC
        """)
        
        result = db.execute(query, {
            "user_id": current_user.id,
            "company_id": current_user.company_id
        }).fetchall()
        
        logger.info(f"✅ Found {len(result)} pending actions")
        
        # Format response
        actions = []
        for row in result:
            action = {
                "id": str(row.id),
                "contract_id": str(row.id),
                "contract_number": row.contract_number,
                "contract_title": row.contract_title,
                "status": row.status,
                "action_type": row.action_type,
                "description": row.description,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "due_date": None,  # Can be added later if needed
                "is_urgent": False,  # Can be calculated based on due_date or other criteria
                "contract_type": row.contract_type,
                "contract_value": float(row.contract_value) if row.contract_value else None,
                "currency": row.currency
            }
            actions.append(action)
            
        logger.info("="*80)
        logger.info(f"✅ PENDING ACTIONS FETCHED SUCCESSFULLY")
        logger.info(f"📊 Total Actions: {len(actions)}")
        logger.info("="*80)
        
        return {
            "success": True,
            "data": actions,
            "count": len(actions)
        }
        
    except Exception as e:
        logger.error("="*80)
        logger.error(f"❌ ERROR FETCHING PENDING ACTIONS")
        logger.error("="*80)
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")
        logger.error("="*80)
        logger.error("Full Traceback:", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))