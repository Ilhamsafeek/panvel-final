# =====================================================
# FILE: app/api/api_v1/blockchain/activity.py
# Blockchain Activity Monitoring Endpoint
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.blockchain_service import blockchain_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/blockchain", tags=["blockchain", "activity"])

# =====================================================
# GET BLOCKCHAIN ACTIVITY FOR CONTRACT
# =====================================================

@router.get("/activity/{contract_id}")
async def get_blockchain_activity(
    contract_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get blockchain activity timeline for a specific contract
    Returns network status, activity logs, and statistics
    """
    try:
        logger.info(f"📊 Fetching blockchain activity for contract {contract_id}")
        
        # =====================================================
        # 1. Get Network Status
        # =====================================================
        network_status = blockchain_service.get_network_status()
        
        # =====================================================
        # 2. Get Audit Logs (Blockchain Operations)
        # =====================================================
        sql_audit = """
            SELECT 
                id,
                user_id,
                contract_id,
                action_type,
                action_details,
                created_at,
                ip_address
            FROM audit_logs
            WHERE contract_id = :contract_id
            AND action_type IN ('blockchain_storage', 'blockchain_verification', 
                               'contract_created', 'contract_updated', 'contract_signed')
            ORDER BY created_at DESC
            LIMIT :limit
        """
        
        result = db.execute(text(sql_audit), {
            "contract_id": contract_id,
            "limit": limit
        })
        
        audit_logs = []
        for row in result:
            # Parse action_details if it's a JSON string
            import json
            try:
                if isinstance(row.action_details, str):
                    action_details = json.loads(row.action_details)
                else:
                    action_details = row.action_details or {}
            except:
                action_details = {"raw": str(row.action_details)}
            
            audit_logs.append({
                "id": row.id,
                "timestamp": row.created_at.isoformat() if row.created_at else None,
                "action": row.action_type,
                "details": action_details,
                "user_id": row.user_id
            })
        
        # =====================================================
        # 3. Get Blockchain Records for Statistics
        # =====================================================
        sql_blockchain = """
            SELECT 
                COUNT(*) as total_count,
                MAX(transaction_hash) as last_hash,
                MAX(created_at) as last_activity
            FROM blockchain_records
            WHERE contract_id = :contract_id
        """
        
        blockchain_result = db.execute(text(sql_blockchain), {
            "contract_id": contract_id
        })
        
        blockchain_stats = blockchain_result.fetchone()
        
        # =====================================================
        # 4. Get Document Integrity Records
        # =====================================================
        sql_integrity = """
            SELECT COUNT(*) as verified_count
            FROM document_integrity
            WHERE contract_id = :contract_id
            AND verified = TRUE
        """
        
        integrity_result = db.execute(text(sql_integrity), {
            "contract_id": contract_id
        })
        
        integrity_stats = integrity_result.fetchone()
        
        # =====================================================
        # 5. Calculate Statistics
        # =====================================================
        statistics = {
            "total_transactions": blockchain_stats.total_count if blockchain_stats else 0,
            "last_block_hash": blockchain_stats.last_hash if blockchain_stats else None,
            "last_activity_time": format_relative_time(
                blockchain_stats.last_activity if blockchain_stats else None
            ),
            "verified_documents": integrity_stats.verified_count if integrity_stats else 0,
            "total_activities": len(audit_logs)
        }
        
        # =====================================================
        # 6. Return Complete Response
        # =====================================================
        logger.info(f"✅ Retrieved {len(audit_logs)} blockchain activities for contract {contract_id}")
        
        return {
            "success": True,
            "contract_id": contract_id,
            "network_status": network_status,
            "activities": audit_logs,
            "statistics": statistics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching blockchain activity: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching blockchain activity: {str(e)}"
        )

# =====================================================
# GET RECENT BLOCKCHAIN ACTIVITY (ALL CONTRACTS)
# =====================================================

@router.get("/activity/recent/all")
async def get_recent_blockchain_activity(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get recent blockchain activity across all contracts
    """
    try:
        logger.info(f"📊 Fetching recent blockchain activity (limit: {limit})")
        
        sql = """
            SELECT 
                al.id,
                al.user_id,
                al.contract_id,
                al.action_type,
                al.action_details,
                al.created_at,
                u.full_name as user_name,
                c.contract_number,
                c.contract_title
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            LEFT JOIN contracts c ON al.contract_id = c.id
            WHERE al.action_type IN ('blockchain_storage', 'blockchain_verification')
            ORDER BY al.created_at DESC
            LIMIT :limit
        """
        
        result = db.execute(text(sql), {"limit": limit})
        
        activities = []
        for row in result:
            import json
            try:
                if isinstance(row.action_details, str):
                    action_details = json.loads(row.action_details)
                else:
                    action_details = row.action_details or {}
            except:
                action_details = {}
            
            activities.append({
                "id": row.id,
                "timestamp": row.created_at.isoformat() if row.created_at else None,
                "action": row.action_type,
                "details": action_details,
                "user_name": row.user_name,
                "contract_number": row.contract_number,
                "contract_title": row.contract_title
            })
        
        logger.info(f"✅ Retrieved {len(activities)} recent blockchain activities")
        
        return {
            "success": True,
            "activities": activities,
            "count": len(activities)
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching recent activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching recent activity: {str(e)}"
        )

# =====================================================
# GET BLOCKCHAIN STATISTICS DASHBOARD
# =====================================================

@router.get("/statistics/dashboard")
async def get_blockchain_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get overall blockchain statistics for dashboard
    """
    try:
        logger.info(f"📊 Fetching blockchain statistics")
        
        # Total blockchain records
        sql_total = "SELECT COUNT(*) as count FROM blockchain_records"
        total_records = db.execute(text(sql_total)).scalar()
        
        # Today's activity
        sql_today = """
            SELECT COUNT(*) as count 
            FROM blockchain_records 
            WHERE DATE(created_at) = CURDATE()
        """
        today_activity = db.execute(text(sql_today)).scalar()
        
        # Verified contracts
        sql_verified = """
            SELECT COUNT(DISTINCT contract_id) as count 
            FROM blockchain_records
        """
        verified_contracts = db.execute(text(sql_verified)).scalar()
        
        # Network status
        network_status = blockchain_service.get_network_status()
        
        return {
            "success": True,
            "statistics": {
                "total_blockchain_records": total_records or 0,
                "today_activity": today_activity or 0,
                "verified_contracts": verified_contracts or 0,
                "network_status": network_status.get("status", "unknown"),
                "peers_count": network_status.get("peers_count", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching blockchain statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching blockchain statistics: {str(e)}"
        )

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def format_relative_time(timestamp):
    """Format timestamp as relative time (e.g., '2 hours ago')"""
    if not timestamp:
        return "Never"
    
    now = datetime.utcnow()
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    diff = now - timestamp
    
    if diff.total_seconds() < 60:
        return "Just now"
    elif diff.total_seconds() < 3600:
        mins = int(diff.total_seconds() / 60)
        return f"{mins} min{'s' if mins > 1 else ''} ago"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = int(diff.total_seconds() / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"