# =====================================================
# FILE: app/api/api_v1/blockchain/router.py
# COMPLETE VERSION - All endpoints including verify-contract-hash
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


logger = logging.getLogger(__name__)
router = APIRouter()


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class VerifyContractRequest(BaseModel):
    contract_id: int


# =====================================================
# ENDPOINTS
# =====================================================

@router.post("/store-contract/{contract_id}")
async def store_contract_on_blockchain(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Store contract on blockchain with detailed activity logging
    """
    try:
        logger.info(f"🔗 Storing contract {contract_id} on blockchain")
        
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access
        if contract.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare contract content for hashing
        contract_content = {
            "contract_number": contract.contract_number,
            "contract_title": contract.contract_title,
            "contract_type": contract.contract_type,
            "contract_value": str(contract.contract_value) if contract.contract_value else "",
            "start_date": str(contract.start_date) if contract.start_date else "",
            "end_date": str(contract.end_date) if contract.end_date else "",
            "created_at": contract.created_at.isoformat() if contract.created_at else ""
        }
        
        # Store with activity logging
        result = await blockchain_service.store_contract_hash_with_logging(
            contract_id=contract_id,
            document_content=contract_content,
            uploaded_by=current_user.id,
            company_id=current_user.company_id,
            db=db
        )
        
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
    Verify contract hash against blockchain
    Accepts JSON body: {"contract_id": 123}
    This is the endpoint called by the frontend
    """
    try:
        contract_id = request.contract_id
        logger.info(f"🔍 Verifying contract hash for contract {contract_id}")
        
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access (optional - can be skipped for verification)
        # if contract.company_id != current_user.company_id:
        #     raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare contract content
        contract_content = {
            "contract_number": contract.contract_number,
            "contract_title": contract.contract_title,
            "contract_type": contract.contract_type,
            "contract_value": str(contract.contract_value) if contract.contract_value else "",
            "start_date": str(contract.start_date) if contract.start_date else "",
            "end_date": str(contract.end_date) if contract.end_date else ""
        }
        
        # Verify
        result = await blockchain_service.verify_contract_hash(
            contract_id=contract_id,
            current_document_content=contract_content
        )
        
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
    Verify contract integrity against blockchain (path parameter version)
    """
    try:
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access
        if contract.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare contract content
        contract_content = {
            "contract_number": contract.contract_number,
            "contract_title": contract.contract_title,
            "contract_type": contract.contract_type,
            "contract_value": str(contract.contract_value) if contract.contract_value else "",
            "start_date": str(contract.start_date) if contract.start_date else "",
            "end_date": str(contract.end_date) if contract.end_date else ""
        }
        
        # Verify
        result = await blockchain_service.verify_contract_hash(
            contract_id=contract_id,
            current_document_content=contract_content
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity-log/{contract_id}")
async def get_blockchain_activity_log(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get blockchain activity log for a contract
    """
    try:
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        # Check access
        if contract.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get activity log
        activities = await blockchain_service.get_blockchain_activity_log(
            contract_id=contract_id,
            db=db
        )
        
        return {
            "success": True,
            "contract_id": contract_id,
            "activities": activities,
            "total_activities": len(activities)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving activity log: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network-status")
async def get_network_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get blockchain network status
    """
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
    """
    Get detailed blockchain transaction information
    """
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
    """
    Get blockchain record for a contract (legacy endpoint)
    """
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
        
        # Return database records
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
            "mode": "database",
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


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "blockchain",
        "network_status": blockchain_service.get_network_status()
    }



# =====================================================
# ADD THIS TO: app/api/api_v1/blockchain/router.py
# Add at the END of the file, before the last line
# =====================================================

# ... (keep all your existing code above)

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
        
        from sqlalchemy import text
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
            WHERE entity_type = 'contract'
            AND entity_id = :contract_id
        """
        
        blockchain_result = db.execute(text(sql_blockchain), {
            "contract_id": str(contract_id)
        })
        
        blockchain_stats = blockchain_result.fetchone()
        
        # =====================================================
        # 4. Get Document Integrity Records
        # =====================================================
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
            status_code=500,
            detail=f"Error fetching blockchain activity: {str(e)}"
        )


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
        
        from sqlalchemy import text
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
            status_code=500,
            detail=f"Error fetching recent activity: {str(e)}"
        )


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
        
        from sqlalchemy import text
        
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
                "peers_count": network_status.get("peers_count", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching blockchain statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching blockchain statistics: {str(e)}"
        )


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def format_relative_time(timestamp):
    """Format timestamp as relative time (e.g., '2 hours ago')"""
    if not timestamp:
        return "Never"
    
    from datetime import datetime
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