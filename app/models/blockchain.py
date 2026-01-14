# =====================================================
# FILE: app/models/blockchain.py
# =====================================================

from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base

class BlockchainRecord(Base):
    """Blockchain transaction records"""
    __tablename__ = "blockchain_records"
    
    id = Column(String(36), primary_key=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(36), nullable=False)
    transaction_hash = Column(String(255), unique=True, nullable=False)
    block_number = Column(String(50))
    blockchain_network = Column(String(50), default="hyperledger-fabric")
    status = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    
    # Add index for faster queries
    __table_args__ = (
        Index('ix_blockchain_entity', 'entity_type', 'entity_id'),
    )

class DocumentIntegrity(Base):
    """Document integrity verification records"""
    __tablename__ = "document_integrity"
    
    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), nullable=False)  # Just a string reference, NO FOREIGN KEY
    hash_algorithm = Column(String(50), default="SHA-256")
    document_hash = Column(String(255), nullable=False)
    blockchain_hash = Column(String(255))
    verification_status = Column(String(50))
    last_verified_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    
    # Add index for faster queries
    __table_args__ = (
        Index('ix_document_integrity_document_id', 'document_id'),
    )