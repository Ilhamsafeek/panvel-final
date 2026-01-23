# =====================================================
# FILE: app/api/api_v1/blockchain/router.py
# Updated for UC032 Comprehensive Hashing
# Service now handles ALL data extraction from database
# =====================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

from app.core.database import get_db
from app.services.blockchain_service import blockchain_service
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.contract import Contract
from app.models.blockchain import BlockchainRecord, DocumentIntegrity

from sqlalchemy import text
from datetime import datetime
import json

from app.api.api_v1.blockchain.terminal import router as terminal_router

logger = logging.getLogger(__name__)
router = APIRouter()

router.include_router(terminal_router, prefix="/terminal")

# =====================================================
# REQUEST SCHEMAS
# =====================================================

class VerifyContractRequest(BaseModel):
    contract_id: int
    document_content: str = ""  # Optional - service fetches from DB


# =====================================================
# CORE BLOCKCHAIN ENDPOINTS
# =====================================================

@router.post("/store-contract/{contract_id}")
async def store_contract_on_blockchain(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Store contract on blockchain with comprehensive hashing
    ✅ UC032 COMPLIANT: Hashes ALL contract fields automatically
    """
    try:
        logger.info(f"🔗 Storing contract {contract_id} on blockchain")
        
        # Get contract for access check
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access
        if contract.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # ✅ NEW: Service handles ALL data extraction from database
        # We just pass contract_id and let service fetch comprehensive data
        result = await blockchain_service.store_contract_hash_with_logging(
            contract_id=contract_id,
            document_content="",  # Ignored - service fetches from DB
            uploaded_by=current_user.id,
            company_id=current_user.company_id,
            db=db  # ✅ CRITICAL: Pass db session
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to store on blockchain")
            )
        
        logger.info(f"✅ Contract {contract_id} stored on blockchain successfully")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error storing contract on blockchain: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-contract-hash")
async def verify_contract_hash_endpoint(
    request: VerifyContractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ✅ UC032 COMPLIANT: Verify contract integrity with comprehensive hashing
    
    This endpoint is called by the frontend verification system.
    Service automatically fetches and hashes ALL contract fields from database.
    
    Request body: {"contract_id": 123}
    """
    try:
        contract_id = request.contract_id
        logger.info(f"🔍 Verifying contract hash for contract {contract_id}")
        
        # Get contract for access check (optional)
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.warning(f"⚠️ Contract {contract_id} not found for verification")
            return {
                "success": False,
                "verified": False,
                "message": "Contract not found"
            }
        
        # ✅ NEW: Service handles ALL data extraction from database
        # document_content parameter is ignored - service fetches comprehensive data
        result = await blockchain_service.verify_contract_hash(
            contract_id=contract_id,
            current_document_content="",  # Ignored - service fetches from DB
            db=db  # ✅ CRITICAL: Pass db session
        )
        
        if result.get("verified"):
            logger.info(f"✅ Contract {contract_id} verification: PASSED")
        else:
            logger.warning(f"🚨 Contract {contract_id} verification: FAILED (tampering detected)")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying contract hash: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify/{contract_id}")
async def verify_contract_integrity(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify contract integrity (path parameter version)
    ✅ UC032 COMPLIANT
    """
    try:
        logger.info(f"🔍 Verifying contract {contract_id} integrity")
        
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access
        if contract.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # ✅ Service handles comprehensive data extraction
        result = await blockchain_service.verify_contract_hash(
            contract_id=contract_id,
            current_document_content="",  # Ignored
            db=db  # ✅ Pass db session
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# BLOCKCHAIN INFORMATION ENDPOINTS
# =====================================================

@router.get("/network-status")
async def get_network_status(
    current_user: User = Depends(get_current_user)
):
    """Get blockchain network status"""
    try:
        status = blockchain_service.get_network_status()
        return {
            "success": True,
            "network_status": status
        }
    except Exception as e:
        logger.error(f"❌ Error getting network status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transaction-details/{contract_id}")
async def get_transaction_details(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed blockchain transaction information"""
    try:
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access
        if contract.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get blockchain record
        blockchain_record = db.query(BlockchainRecord).filter(
            BlockchainRecord.entity_type == "contract",
            BlockchainRecord.entity_id == str(contract_id)
        ).first()
        
        # Get integrity record
        integrity_record = db.query(DocumentIntegrity).filter(
            DocumentIntegrity.document_id == str(contract_id)
        ).first()
        
        if not blockchain_record or not integrity_record:
            return {
                "success": False,
                "message": "No blockchain record found. Please save the contract first.",
                "blockchain_record": None,
                "integrity_record": None
            }
        
        return {
            "success": True,
            "contract_id": contract_id,
            "contract_number": contract.contract_number,
            "blockchain_record": {
                "transaction_hash": blockchain_record.transaction_hash,
                "block_number": blockchain_record.block_number,
                "network": blockchain_record.blockchain_network,
                "status": blockchain_record.status,
                "created_at": blockchain_record.created_at.isoformat()
            },
            "integrity_record": {
                "document_hash": integrity_record.document_hash,
                "hash_algorithm": integrity_record.hash_algorithm,
                "verification_status": integrity_record.verification_status,
                "last_verified_at": integrity_record.last_verified_at.isoformat() if integrity_record.last_verified_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting transaction details: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contract-record/{contract_id}")
async def get_contract_record(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get blockchain record for a contract"""
    try:
        logger.info(f"🔍 Getting blockchain record for contract {contract_id}")
        
        # Get blockchain record
        blockchain_record = db.query(BlockchainRecord).filter(
            BlockchainRecord.entity_type == "contract",
            BlockchainRecord.entity_id == str(contract_id)
        ).first()
        
        # Get integrity record
        integrity_record = db.query(DocumentIntegrity).filter(
            DocumentIntegrity.document_id == str(contract_id)
        ).first()
        
        if not blockchain_record and not integrity_record:
            return {
                "success": False,
                "message": "No blockchain record found. Please save the contract first.",
                "blockchain_record": None,
                "integrity_record": None
            }
        
        return {
            "success": True,
            "blockchain_record": {
                "transaction_hash": blockchain_record.transaction_hash if blockchain_record else "N/A",
                "block_number": blockchain_record.block_number if blockchain_record else "N/A",
                "network": blockchain_record.blockchain_network if blockchain_record else "hyperledger-fabric",
                "status": blockchain_record.status if blockchain_record else "N/A",
                "created_at": blockchain_record.created_at.isoformat() if blockchain_record else None
            },
            "integrity_record": {
                "document_hash": integrity_record.document_hash if integrity_record else "N/A",
                "verification_status": integrity_record.verification_status if integrity_record else "N/A",
                "last_verified_at": integrity_record.last_verified_at.isoformat() if integrity_record and integrity_record.last_verified_at else None
            },
            "mode": "comprehensive_hashing",
            "source": "mysql_database"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting record: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": str(e),
            "blockchain_record": None,
            "integrity_record": None
        }


@router.get("/contract-history/{contract_id}")
async def get_contract_blockchain_history(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get blockchain history for a contract"""
    try:
        # Get all blockchain records
        records = db.execute(text("""
            SELECT 
                br.id,
                br.transaction_hash,
                br.block_number,
                br.blockchain_network,
                br.status,
                br.created_at,
                di.document_hash,
                di.verification_status,
                di.last_verified_at
            FROM blockchain_records br
            LEFT JOIN document_integrity di ON br.entity_id = di.document_id
            WHERE br.entity_type = 'contract' 
                AND br.entity_id = :contract_id
            ORDER BY br.created_at DESC
        """), {"contract_id": str(contract_id)}).fetchall()
        
        history = []
        for record in records:
            history.append({
                "id": record.id,
                "transaction_hash": record.transaction_hash,
                "block_number": record.block_number,
                "network": record.blockchain_network,
                "status": record.status,
                "document_hash": record.document_hash,
                "verification_status": record.verification_status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "last_verified_at": record.last_verified_at.isoformat() if record.last_verified_at else None
            })
        
        return {
            "success": True,
            "contract_id": contract_id,
            "total_records": len(history),
            "history": history
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting contract history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tamper-events/{contract_id}")
async def get_tamper_events(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get tamper events for a contract"""
    try:
        events = db.execute(text("""
            SELECT 
                id,
                document_id,
                detected_at,
                current_hash,
                stored_hash,
                response_action,
                resolved,
                resolved_at
            FROM tamper_events
            WHERE document_id = :contract_id
            ORDER BY detected_at DESC
        """), {"contract_id": str(contract_id)}).fetchall()
        
        tamper_events = []
        for event in events:
            tamper_events.append({
                "id": event.id,
                "document_id": event.document_id,
                "detected_at": event.detected_at.isoformat() if event.detected_at else None,
                "current_hash": event.current_hash[:16] + "..." if event.current_hash else None,
                "stored_hash": event.stored_hash[:16] + "..." if event.stored_hash else None,
                "response_action": event.response_action,
                "resolved": event.resolved,
                "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None
            })
        
        return {
            "success": True,
            "contract_id": contract_id,
            "total_events": len(tamper_events),
            "events": tamper_events
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting tamper events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# BLOCKCHAIN ACTIVITY MONITORING ENDPOINTS
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
        
        # Get network status
        network_status = blockchain_service.get_network_status()
        
        # Get audit logs
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
        
        # Get blockchain statistics
        sql_blockchain = """
            SELECT 
                COUNT(*) as total_count,
                MAX(transaction_hash) as last_hash,
                MAX(created_at) as last_activity
            FROM blockchain_records
            WHERE entity_type = 'contract'
            AND entity_id = :contract_id
        """
        
        blockchain_result = db.execute(text(sql_blockchain), {
            "contract_id": str(contract_id)
        })
        
        blockchain_stats = blockchain_result.fetchone()
        
        # Get integrity statistics
        sql_integrity = """
            SELECT COUNT(*) as verified_count
            FROM document_integrity
            WHERE document_id = :contract_id
            AND verification_status = 'verified'
        """
        
        integrity_result = db.execute(text(sql_integrity), {
            "contract_id": str(contract_id)
        })
        
        integrity_stats = integrity_result.fetchone()
        
        # Calculate statistics
        statistics = {
            "total_transactions": blockchain_stats.total_count if blockchain_stats else 0,
            "last_block_hash": blockchain_stats.last_hash if blockchain_stats else None,
            "last_activity_time": format_relative_time(
                blockchain_stats.last_activity if blockchain_stats else None
            ),
            "verified_documents": integrity_stats.verified_count if integrity_stats else 0,
            "total_activities": len(audit_logs)
        }
        
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
            status_code=500,
            detail=f"Error fetching blockchain activity: {str(e)}"
        )


@router.get("/activity/recent/all")
async def get_recent_blockchain_activity(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent blockchain activity across all contracts"""
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
            status_code=500,
            detail=f"Error fetching recent activity: {str(e)}"
        )


@router.get("/statistics/dashboard")
async def get_blockchain_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall blockchain statistics for dashboard"""
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
            SELECT COUNT(DISTINCT entity_id) as count 
            FROM blockchain_records
            WHERE entity_type = 'contract'
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
                "peers_count": network_status.get("peers_count", 0),
                "hashing_mode": "comprehensive (UC032 compliant)"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching blockchain statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching blockchain statistics: {str(e)}"
        )


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "blockchain",
        "version": "UC032_comprehensive_hashing_v2.0",
        "network_status": blockchain_service.get_network_status()
    }


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