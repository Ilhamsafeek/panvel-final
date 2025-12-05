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