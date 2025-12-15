from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from pydantic import BaseModel

router = APIRouter()

# =====================================================
# SCHEMAS
# =====================================================

class NegotiationSessionCreate(BaseModel):
    contract_id: str
    session_type: str  # internal or external
    participant_ids: List[str] = []

class MessageCreate(BaseModel):
    session_id: str
    message_content: str
    message_type: str = "text"  # text, clause_change, system

class MessageResponse(BaseModel):
    id: str
    sender_name: str
    sender_type: str
    message_content: str
    message_type: str
    created_at: str
    is_ai_generated: bool = False

# =====================================================
# START NEGOTIATION SESSION
# =====================================================

@router.post("/sessions/start")
async def start_negotiation_session(
    data: NegotiationSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new negotiation session"""
    try:
        session_id = str(uuid.uuid4())
        session_code = f"NEG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Convert contract_id to integer and validate
        try:
            contract_id = int(data.contract_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid contract_id format: '{data.contract_id}'. Expected integer."
            )
        
        # Verify contract exists
        contract_check = db.execute(
            text("SELECT id, contract_title FROM contracts WHERE id = :contract_id"),
            {"contract_id": contract_id}
        ).fetchone()
        
        if not contract_check:
            # Get list of available contracts for debugging
            available = db.execute(
                text("""
                    SELECT id, contract_title, status 
                    FROM contracts 
                    WHERE created_by = :user_id OR company_id = :company_id
                    ORDER BY id DESC LIMIT 5
                """),
                {"user_id": current_user.id, "company_id": current_user.company_id}
            ).fetchall()
            
            available_ids = [str(c.id) for c in available] if available else []
            
            raise HTTPException(
                status_code=404, 
                detail=f"Contract ID {contract_id} not found. Available contracts: {', '.join(available_ids) if available_ids else 'None'}"
            )
        
        # Check if an active session already exists for this contract
        existing_session = db.execute(
            text("""
                SELECT id, session_code, status 
                FROM negotiation_sessions 
                WHERE contract_id = :contract_id AND status = 'active'
            """),
            {"contract_id": contract_id}
        ).fetchone()
        
        if existing_session:
            session_id = existing_session.id
            session_code = existing_session.session_code
            
            # Check if current user is already a participant
            is_participant = db.execute(
                text("""
                    SELECT id FROM negotiation_participants 
                    WHERE session_id = :session_id AND user_id = :user_id
                """),
                {"session_id": session_id, "user_id": current_user.id}
            ).fetchone()
            
            # If not a participant, add them
            if not is_participant:
                db.execute(
                    text("""
                    INSERT INTO negotiation_participants 
                    (id, session_id, user_id, company_id, role, is_active)
                    VALUES (:id, :session_id, :user_id, :company_id, 'participant', 1)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "user_id": current_user.id,
                        "company_id": current_user.company_id
                    }
                )
                
                # Add system message
                user_full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
                if not user_full_name:
                    user_full_name = current_user.email
                
                db.execute(
                    text("""
                    INSERT INTO negotiation_messages 
                    (id, session_id, sender_id, message_type, message_content, is_ai_generated)
                    VALUES (:id, :session_id, :sender_id, 'system', :message_content, 0)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "sender_id": current_user.id,
                        "message_content": f"{user_full_name} joined the negotiation"
                    }
                )
                
                db.commit()
            
            return {
                "success": True,
                "session_id": session_id,
                "session_code": session_code,
                "session_type": data.session_type,
                "message": "Joined existing negotiation session"
            }
        
        # Create new session if none exists
        db.execute(
            text("""
            INSERT INTO negotiation_sessions 
            (id, contract_id, session_code, initiator_id, status, start_time)
            VALUES (:session_id, :contract_id, :session_code, :initiator_id, 'active', NOW())
            """),
            {
                "session_id": session_id,
                "contract_id": contract_id,
                "session_code": session_code,
                "initiator_id": current_user.id
            }
        )
        
        # Add initiator as participant
        db.execute(
            text("""
            INSERT INTO negotiation_participants 
            (id, session_id, user_id, company_id, role, is_active)
            VALUES (:id, :session_id, :user_id, :company_id, 'initiator', 1)
            """),
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": current_user.id,
                "company_id": current_user.company_id
            }
        )
        
        # Add other participants based on session type
        if data.session_type == "internal":
            # Get workflow participants
            workflow_users = db.execute(
                text("""
                SELECT DISTINCT ws.approver_user_id as user_id, u.company_id
                FROM workflow_stages ws
                JOIN workflow_instances wi ON ws.workflow_instance_id = wi.id
                JOIN users u ON ws.approver_user_id = u.id
                WHERE wi.contract_id = :contract_id AND ws.approver_user_id IS NOT NULL
                """),
                {"contract_id": contract_id}
            ).fetchall()
            
            for user in workflow_users:
                if user.user_id != current_user.id:
                    db.execute(
                        text("""
                        INSERT INTO negotiation_participants 
                        (id, session_id, user_id, company_id, role, is_active)
                        VALUES (:id, :session_id, :user_id, :company_id, 'participant', 1)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "session_id": session_id,
                            "user_id": user.user_id,
                            "company_id": user.company_id
                        }
                    )
        
        elif data.session_type == "external":
            # Get contract initiator
            contract_data = db.execute(
                text("""
                SELECT created_by, company_id FROM contracts WHERE id = :contract_id
                """),
                {"contract_id": contract_id}
            ).fetchone()
            
            if contract_data and contract_data.created_by != current_user.id:
                db.execute(
                    text("""
                    INSERT INTO negotiation_participants 
                    (id, session_id, user_id, company_id, role, is_active)
                    VALUES (:id, :session_id, :user_id, :company_id, 'counterparty', 1)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "user_id": contract_data.created_by,
                        "company_id": contract_data.company_id
                    }
                )
        
        # Get user full name
        user_full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
        if not user_full_name:
            user_full_name = current_user.email
        
        # Add system message
        db.execute(
            text("""
            INSERT INTO negotiation_messages 
            (id, session_id, sender_id, message_type, message_content, is_ai_generated)
            VALUES (:id, :session_id, :sender_id, 'system', :message_content, 0)
            """),
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "sender_id": current_user.id,
                "message_content": f"Negotiation session started by {user_full_name}"
            }
        )
        
        db.commit()
        
        return {
            "success": True,
            "session_id": session_id,
            "session_code": session_code,
            "session_type": data.session_type
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

# =====================================================
# GET SESSION DETAILS
# =====================================================

@router.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get negotiation session details"""
    try:
        # Get session
        session = db.execute(
            text("""
            SELECT 
                ns.*,
                c.contract_title,
                CONCAT(u.first_name, ' ', u.last_name) as initiator_name
            FROM negotiation_sessions ns
            JOIN contracts c ON ns.contract_id = c.id
            JOIN users u ON ns.initiator_id = u.id
            WHERE ns.id = :session_id
            """),
            {"session_id": session_id}
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get participants
        participants = db.execute(
            text("""
            SELECT 
                np.*,
                CONCAT(u.first_name, ' ', u.last_name) as full_name,
                u.email,
                c.company_name
            FROM negotiation_participants np
            JOIN users u ON np.user_id = u.id
            LEFT JOIN companies c ON np.company_id = c.id
            WHERE np.session_id = :session_id AND np.is_active = 1
            """),
            {"session_id": session_id}
        ).fetchall()
        
        return {
            "success": True,
            "session": dict(session._mapping),
            "participants": [dict(p._mapping) for p in participants]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# SEND MESSAGE
# =====================================================

@router.post("/messages/send")
async def send_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message in negotiation session"""
    try:
        message_id = str(uuid.uuid4())
        
        # Verify user is participant
        participant = db.execute(
            text("""
            SELECT id FROM negotiation_participants 
            WHERE session_id = :session_id AND user_id = :user_id AND is_active = 1
            """),
            {"session_id": data.session_id, "user_id": current_user.id}
        ).fetchone()
        
        if not participant:
            raise HTTPException(status_code=403, detail="Not a participant")
        
        # Insert message
        db.execute(
            text("""
            INSERT INTO negotiation_messages 
            (id, session_id, sender_id, message_type, message_content, is_ai_generated, created_at)
            VALUES (:id, :session_id, :sender_id, :message_type, :message_content, 0, NOW())
            """),
            {
                "id": message_id,
                "session_id": data.session_id,
                "sender_id": current_user.id,
                "message_type": data.message_type,
                "message_content": data.message_content
            }
        )
        
        db.commit()
        
        # Get user full name
        user_full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
        if not user_full_name:
            user_full_name = current_user.email
        
        # Return formatted message
        return {
            "success": True,
            "message": {
                "id": message_id,
                "sender_name": user_full_name,
                "sender_type": "current_user",  # ← FIXED: was "user"
                "message_content": data.message_content,
                "message_type": data.message_type,
                "created_at": datetime.now().isoformat(),
                "is_ai_generated": False
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# GET MESSAGES
# =====================================================

@router.get("/messages/{session_id}")
async def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all messages for a session"""
    try:
        messages = db.execute(
            text("""
            SELECT 
                nm.id,
                nm.message_content,
                nm.message_type,
                nm.is_ai_generated,
                nm.created_at,
                CONCAT(u.first_name, ' ', u.last_name) as sender_name,
                u.id as sender_id,
                CASE 
                    WHEN nm.is_ai_generated = 1 THEN 'ai'
                    WHEN nm.sender_id = :current_user_id THEN 'current_user'
                    ELSE 'other_user'
                END as sender_type
            FROM negotiation_messages nm
            JOIN users u ON nm.sender_id = u.id
            WHERE nm.session_id = :session_id
            ORDER BY nm.created_at ASC
            """),
            {"current_user_id": current_user.id, "session_id": session_id}
        ).fetchall()
        
        return {
            "success": True,
            "messages": [
                {
                    "id": msg.id,
                    "sender_name": msg.sender_name or 'Unknown',
                    "sender_type": msg.sender_type,
                    "message_content": msg.message_content,
                    "message_type": msg.message_type,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "is_ai_generated": bool(msg.is_ai_generated)
                }
                for msg in messages
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# END SESSION
# =====================================================

@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    outcome: str = "completed",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """End a negotiation session"""
    try:
        db.execute(
            text("""
            UPDATE negotiation_sessions 
            SET status = 'ended', end_time = NOW(), outcome = :outcome
            WHERE id = :session_id
            """),
            {"outcome": outcome, "session_id": session_id}
        )
        
        db.execute(
            text("""
            UPDATE negotiation_participants 
            SET is_active = 0, left_at = NOW()
            WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        )
        
        db.commit()
        
        return {"success": True, "message": "Session ended"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# DOWNLOAD MINUTES
# =====================================================

@router.get("/sessions/{session_id}/minutes")
async def download_minutes(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get session minutes for download"""
    try:
        # Get session details
        session = db.execute(
            text("""
            SELECT 
                ns.*,
                c.contract_title,
                CONCAT(u.first_name, ' ', u.last_name) as initiator_name
            FROM negotiation_sessions ns
            JOIN contracts c ON ns.contract_id = c.id
            JOIN users u ON ns.initiator_id = u.id
            WHERE ns.id = :session_id
            """),
            {"session_id": session_id}
        ).fetchone()
        
        # Get all messages
        messages = db.execute(
            text("""
            SELECT 
                nm.message_content,
                nm.message_type,
                nm.created_at,
                CONCAT(u.first_name, ' ', u.last_name) as sender_name
            FROM negotiation_messages nm
            JOIN users u ON nm.sender_id = u.id
            WHERE nm.session_id = :session_id
            ORDER BY nm.created_at ASC
            """),
            {"session_id": session_id}
        ).fetchall()
        
        # Format minutes
        minutes_text = f"""
NEGOTIATION SESSION MINUTES
Session Code: {session.session_code}
Contract: {session.contract_title}
Started: {session.start_time}
Status: {session.status}

TRANSCRIPT:
{'='*50}

"""
        for msg in messages:
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else ''
            sender = msg.sender_name or 'Unknown'
            minutes_text += f"[{timestamp}] {sender}: {msg.message_content}\n\n"
        
        return {
            "success": True,
            "minutes": minutes_text,
            "filename": f"Negotiation_Minutes_{session.session_code}.txt"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))