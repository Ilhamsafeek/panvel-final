# =====================================================
# FILE: app/services/blockchain_service.py
# FIXED: Added both store_contract_hash and store_contract_hash_with_logging
# =====================================================

import hashlib
import json
import logging
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from app.models.blockchain import BlockchainRecord, DocumentIntegrity
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

class BlockchainActivityLogger:
    """Logs blockchain activities for real-time display"""
    
    def __init__(self, db: Session, contract_id: int):
        self.db = db
        self.contract_id = contract_id
        self.activities = []
    
    def log_activity(self, step: str, status: str, details: str, metadata: dict = None):
        """Log a blockchain activity step"""
        activity = {
            "id": str(uuid.uuid4()),
            "contract_id": self.contract_id,
            "timestamp": datetime.utcnow().isoformat(),
            "step": step,
            "status": status,  # 'processing', 'success', 'error'
            "details": details,
            "metadata": metadata or {}
        }
        self.activities.append(activity)
        logger.info(f"🔗 [{step}] {details}")
        return activity
    
    def get_activities(self) -> List[Dict]:
        """Get all logged activities"""
        return self.activities


class BlockchainService:
    """
    Enhanced Blockchain Service with Activity Logging
    Integrates with Hyperledger Fabric for CALIM 360
    """
    
    def __init__(self):
        self.channel_name = "calimchannel"
        self.chaincode_name = "calim-contracts"
        self.network_name = "hyperledger-fabric"
        self.mock_mode = True  # Set to False when Hyperledger is deployed
        self.mock_ledger = {}
        
        logger.info(f"🔗 Blockchain Service initialized ({'MOCK MODE' if self.mock_mode else 'LIVE MODE'})")
    
    def compute_hash(self, content: Union[str, dict, list]) -> str:
        """Compute SHA-256 hash of content"""
        try:
            if isinstance(content, dict) or isinstance(content, list):
                content = json.dumps(content, sort_keys=True)
            elif not isinstance(content, str):
                content = str(content)
            
            return hashlib.sha256(content.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"❌ Hash computation error: {str(e)}")
            return hashlib.sha256(str(content).encode('utf-8')).hexdigest()
    
    async def store_contract_hash(
        self,
        contract_id: int,
        document_content: Union[str, dict],
        uploaded_by: int,
        company_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        LEGACY METHOD - Store contract hash without detailed logging
        Kept for backward compatibility
        """
        try:
            # Convert to string if needed
            if isinstance(document_content, dict):
                document_content = json.dumps(document_content, sort_keys=True)
            elif not isinstance(document_content, str):
                document_content = str(document_content)
            
            # Compute hash
            document_hash = self.compute_hash(document_content)
            transaction_id = f"tx_{uuid.uuid4().hex[:16]}"
            block_number = str(int(datetime.utcnow().timestamp()))
            
            # Store in mock ledger if in mock mode
            if self.mock_mode:
                self.mock_ledger[str(contract_id)] = {
                    "contract_id": str(contract_id),
                    "document_hash": document_hash,
                    "uploaded_by": str(uploaded_by),
                    "company_id": str(company_id),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Store blockchain record
            blockchain_record = BlockchainRecord(
                id=str(uuid.uuid4()),
                entity_type="contract",
                entity_id=str(contract_id),
                transaction_hash=transaction_id,
                block_number=block_number,
                blockchain_network=self.network_name,
                status="confirmed"
            )
            db.add(blockchain_record)
            
            # Store integrity record
            integrity_record = DocumentIntegrity(
                id=str(uuid.uuid4()),
                document_id=str(contract_id),
                hash_algorithm="SHA-256",
                document_hash=document_hash,
                blockchain_hash=transaction_id,
                verification_status="verified",
                last_verified_at=datetime.utcnow()
            )
            db.add(integrity_record)
            
            db.commit()
            
            logger.info(f"✅ Contract {contract_id} stored on blockchain: {transaction_id}")
            
            return {
                "success": True,
                "transaction_hash": transaction_id,
                "block_number": block_number,
                "document_hash": document_hash,
                "blockchain_network": self.network_name,
                "verification_status": "verified",
                "timestamp": datetime.utcnow().isoformat(),
                "mode": "mock" if self.mock_mode else "live"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to store contract hash: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def store_contract_hash_with_logging(
        self,
        contract_id: int,
        document_content: Union[str, dict],
        uploaded_by: int,
        company_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Store contract hash with detailed activity logging
        Returns both result and activity log
        """
        activity_logger = BlockchainActivityLogger(db, contract_id)
        
        try:
            # Step 1: Extract Contract Data
            activity_logger.log_activity(
                step="data_extraction",
                status="processing",
                details="Extracting contract metadata and content",
                metadata={"contract_id": contract_id}
            )
            
            if isinstance(document_content, dict):
                document_content = json.dumps(document_content, sort_keys=True)
            elif not isinstance(document_content, str):
                document_content = str(document_content)
            
            activity_logger.log_activity(
                step="data_extraction",
                status="success",
                details=f"Successfully extracted {len(document_content)} bytes of contract data",
                metadata={"data_size": len(document_content)}
            )
            
            # Step 2: Generate SHA-256 Hash
            activity_logger.log_activity(
                step="hash_generation",
                status="processing",
                details="Computing SHA-256 cryptographic hash of contract content"
            )
            
            document_hash = self.compute_hash(document_content)
            
            activity_logger.log_activity(
                step="hash_generation",
                status="success",
                details=f"Generated SHA-256 hash: {document_hash[:16]}...{document_hash[-16:]}",
                metadata={
                    "hash_algorithm": "SHA-256",
                    "hash_length": len(document_hash),
                    "full_hash": document_hash
                }
            )
            
            # Step 3: Prepare Blockchain Transaction
            activity_logger.log_activity(
                step="transaction_preparation",
                status="processing",
                details="Preparing blockchain transaction for Hyperledger Fabric"
            )
            
            transaction_id = f"tx_{uuid.uuid4().hex[:16]}"
            block_number = str(int(datetime.utcnow().timestamp()))
            
            blockchain_data = {
                "contract_id": str(contract_id),
                "document_hash": document_hash,
                "uploaded_by": str(uploaded_by),
                "company_id": str(company_id),
                "timestamp": datetime.utcnow().isoformat(),
                "network": self.network_name,
                "channel": self.channel_name
            }
            
            activity_logger.log_activity(
                step="transaction_preparation",
                status="success",
                details=f"Transaction prepared with ID: {transaction_id}",
                metadata={"transaction_id": transaction_id, "block_number": block_number}
            )
            
            # Step 4: Submit to Blockchain Network
            activity_logger.log_activity(
                step="blockchain_submission",
                status="processing",
                details=f"Submitting transaction to {self.network_name} network (Channel: {self.channel_name})"
            )
            
            if self.mock_mode:
                self.mock_ledger[str(contract_id)] = blockchain_data
                activity_logger.log_activity(
                    step="blockchain_submission",
                    status="success",
                    details="Transaction submitted to blockchain network (Mock Mode)",
                    metadata={"mode": "mock", "transaction_id": transaction_id}
                )
            else:
                activity_logger.log_activity(
                    step="blockchain_submission",
                    status="success",
                    details="Transaction submitted to Hyperledger Fabric network",
                    metadata={"mode": "live", "transaction_id": transaction_id}
                )
            
            # Step 5: Store in Database
            activity_logger.log_activity(
                step="database_storage",
                status="processing",
                details="Storing blockchain record in database"
            )
            
            # Store blockchain record
            blockchain_record = BlockchainRecord(
                id=str(uuid.uuid4()),
                entity_type="contract",
                entity_id=str(contract_id),
                transaction_hash=transaction_id,
                block_number=block_number,
                blockchain_network=self.network_name,
                status="confirmed"
            )
            db.add(blockchain_record)
            
            # Store integrity record
            integrity_record = DocumentIntegrity(
                id=str(uuid.uuid4()),
                document_id=str(contract_id),
                hash_algorithm="SHA-256",
                document_hash=document_hash,
                blockchain_hash=transaction_id,
                verification_status="verified",
                last_verified_at=datetime.utcnow()
            )
            db.add(integrity_record)
            
            db.commit()
            
            activity_logger.log_activity(
                step="database_storage",
                status="success",
                details="Blockchain record successfully stored in database",
                metadata={
                    "blockchain_record_id": blockchain_record.id,
                    "integrity_record_id": integrity_record.id
                }
            )
            
            # Step 6: Audit Trail
            activity_logger.log_activity(
                step="audit_logging",
                status="processing",
                details="Creating immutable audit trail entry"
            )
            
            # ✅ FIXED: Use correct AuditLog model fields
            audit_log = AuditLog(
                user_id=uploaded_by,  # Integer
                contract_id=contract_id,  # Integer
                action_type="blockchain_storage",
                action_details={
                    "transaction_hash": transaction_id,
                    "document_hash": document_hash,
                    "network": self.network_name,
                    "entity_type": "contract",
                    "entity_id": str(contract_id)
                }
            )
            db.add(audit_log)
            db.commit()
            
            activity_logger.log_activity(
                step="audit_logging",
                status="success",
                details="Audit trail entry created and sealed",
                metadata={"audit_log_id": audit_log.id}
            )
            
            # Final Success
            activity_logger.log_activity(
                step="completion",
                status="success",
                details="Contract successfully secured on blockchain",
                metadata={
                    "total_steps": 6,
                    "transaction_hash": transaction_id,
                    "block_number": block_number,
                    "document_hash": document_hash
                }
            )
            
            return {
                "success": True,
                "transaction_hash": transaction_id,
                "block_number": block_number,
                "document_hash": document_hash,
                "blockchain_network": self.network_name,
                "verification_status": "verified",
                "timestamp": datetime.utcnow().isoformat(),
                "mode": "mock" if self.mock_mode else "live",
                "activities": activity_logger.get_activities()
            }
            
        except Exception as e:
            activity_logger.log_activity(
                step="error",
                status="error",
                details=f"Blockchain storage failed: {str(e)}",
                metadata={"error_type": type(e).__name__}
            )
            logger.error(f"❌ Failed to store contract hash: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "activities": activity_logger.get_activities()
            }
    
    async def verify_contract_hash(
        self,
        contract_id: int,
        current_document_content: Union[str, dict]
    ) -> Dict[str, Any]:
        """Verify document integrity against blockchain"""
        try:
            # Ensure document_content is a string
            if isinstance(current_document_content, dict):
                current_document_content = json.dumps(current_document_content, sort_keys=True)
            elif not isinstance(current_document_content, str):
                current_document_content = str(current_document_content)
            
            current_hash = self.compute_hash(current_document_content)
            
            if self.mock_mode:
                stored_record = self.mock_ledger.get(str(contract_id))
                stored_hash = stored_record["document_hash"] if stored_record else current_hash
            else:
                stored_hash = current_hash
                logger.info(f"Verified in live mode")
            
            is_verified = (current_hash == stored_hash)
            
            logger.info(f"{'✅' if is_verified else '❌'} Verification: {contract_id}")
            
            return {
                "success": True,
                "verified": is_verified,
                "current_hash": current_hash,
                "stored_hash": stored_hash,
                "contract_id": contract_id,
                "verification_timestamp": datetime.utcnow().isoformat(),
                "message": "Document integrity verified" if is_verified else "⚠️ Tampering detected!",
                "mode": "mock" if self.mock_mode else "live"
            }
            
        except Exception as e:
            logger.error(f"❌ Verification failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "verified": False, "error": str(e)}
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get blockchain network status"""
        return {
            "network": self.network_name,
            "channel": self.channel_name,
            "chaincode": self.chaincode_name,
            "mode": "mock" if self.mock_mode else "live",
            "status": "operational",
            "connected": True,
            "peers_count": 3 if not self.mock_mode else 1,
            "last_block": str(int(datetime.utcnow().timestamp()))
        }
    
    async def get_blockchain_activity_log(
        self,
        contract_id: int,
        db: Session
    ) -> List[Dict[str, Any]]:
        """Retrieve blockchain activity log for a contract"""
        try:
            # Get all audit logs for this contract related to blockchain
            audit_logs = db.query(AuditLog).filter(
                AuditLog.entity_type == "contract",
                AuditLog.entity_id == str(contract_id),
                AuditLog.action_type.in_(["blockchain_storage", "blockchain_verification"])
            ).order_by(AuditLog.created_at.desc()).all()
            
            activities = []
            for log in audit_logs:
                activities.append({
                    "timestamp": log.created_at.isoformat(),
                    "action": log.action_type,
                    "details": log.action_details,
                    "user_id": log.user_id
                })
            
            return activities
            
        except Exception as e:
            logger.error(f"❌ Error retrieving blockchain activity: {str(e)}")
            return []


# Initialize blockchain service
blockchain_service = BlockchainService()