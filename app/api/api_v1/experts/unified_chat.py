# =====================================================
# FILE: app/api/api_v1/experts/unified_chat.py
# Ask an Expert - Unified Chat API (FIXED for actual DB)
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from typing import List, Optional
from datetime import datetime
import logging
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# =====================================================
# PYDANTIC SCHEMAS
# =====================================================

class SessionCreate(BaseModel):
    expert_id: str
    session_type: str = "chat"
    subject: str
    question: str

class MessageCreate(BaseModel):
    message_content: str
    message_type: str = "text"

# =====================================================
# GET EXPERT DIRECTORY
# =====================================================
@router.get("/directory")
async def get_expert_directory(
    search: Optional[str] = None,
    expertise_area: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get expert directory with search and filters"""
    try:
        where_conditions = [
            "u.is_active = 1",
            "ep.id IS NOT NULL"
        ]
        params = {}
        
        # Search
        if search:
            where_conditions.append("""
                (LOWER(u.first_name) LIKE LOWER(:search) 
                OR LOWER(u.last_name) LIKE LOWER(:search)
                OR LOWER(u.email) LIKE LOWER(:search)
                OR LOWER(u.department) LIKE LOWER(:search)
                OR LOWER(ep.expertise_areas) LIKE LOWER(:search))
            """)
            params["search"] = f"%{search}%"
        
        # Filter by expertise area
        if expertise_area:
            where_conditions.append("LOWER(ep.expertise_areas) LIKE LOWER(:expertise)")
            params["expertise"] = f"%{expertise_area}%"
        
        where_clause = " AND ".join(where_conditions)
        
        # Main query
        query_sql = text(f"""
            SELECT 
                ep.id AS expert_id,
                u.first_name,
                u.last_name,
                CONCAT(u.first_name, ' ', u.last_name) AS full_name,
                u.email,
                u.profile_picture_url AS profile_picture,
                u.department,
                u.job_title,
                ep.is_available,
                ep.expertise_areas,
                ep.specialization,
                ep.license_number,
                ep.years_of_experience,
                ep.bio,
                ep.hourly_rate,
                ep.total_consultations,
                ep.average_rating,
                ep.qfcra_certified,
                ep.qid_verified
            FROM users u
            INNER JOIN expert_profiles ep ON u.id = ep.user_id
            WHERE {where_clause}
            ORDER BY ep.total_consultations DESC, ep.average_rating DESC
            LIMIT :limit OFFSET :offset
        """)
        
        params["limit"] = limit
        params["offset"] = offset
        
        result = db.execute(query_sql, params)
        rows = result.fetchall()
        
        # Count total
        count_sql = text(f"""
            SELECT COUNT(*) 
            FROM users u
            INNER JOIN expert_profiles ep ON u.id = ep.user_id
            WHERE {where_clause}
        """)
        count_result = db.execute(count_sql, {k: v for k, v in params.items() if k not in ['limit', 'offset']})
        total_count = count_result.scalar()
        
        experts = []
        for row in rows:
            # Parse expertise areas from JSON string
            import json
            expertise_list = []
            if row[9]:  # expertise_areas
                try:
                    expertise_list = json.loads(row[9]) if isinstance(row[9], str) else row[9]
                except:
                    expertise_list = [row[9]] if row[9] else []
            
            experts.append({
                "expert_id": str(row[0]),
                "first_name": row[1],
                "last_name": row[2],
                "full_name": row[3],
                "email": row[4],
                "profile_picture": row[5],
                "department": row[6],
                "job_title": row[7],
                "is_available": bool(row[8]),
                "expertise_areas": expertise_list,
                "specialization": row[10],
                "license_number": row[11],
                "years_of_experience": row[12] or 0,
                "bio": row[13],
                "hourly_rate": float(row[14]) if row[14] else 0.0,
                "total_consultations": row[15] or 0,
                "average_rating": float(row[16]) if row[16] else 0.0,
                "qfcra_certified": bool(row[17]),
                "qid_verified": bool(row[18])
            })
        
        return {
            "success": True,
            "experts": experts,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
    except Exception as e:
        logger.error(f"Error loading expert directory: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# GET MY CONSULTATIONS (Chat History)
# =====================================================
@router.get("/my-consultations")
async def get_my_consultations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all consultation sessions for the current user
    Shows sessions where user is either the client or the expert
    """
    try:
        # Determine if user is an expert
        check_expert_sql = text("""
            SELECT id FROM expert_profiles 
            WHERE user_id = :user_id
        """)
        expert_result = db.execute(check_expert_sql, {"user_id": current_user.id})
        expert_row = expert_result.fetchone()
        is_expert = expert_row is not None
        expert_profile_id = expert_row[0] if is_expert else None
        
        # Build query based on user type - REMOVED is_read reference
        # IMPORTANT: Only show expert consultations, NOT AI chatbot sessions
        if is_expert:
            # Expert sees sessions assigned to them
            query_sql = text("""
                SELECT 
                    es.id AS session_id,
                    es.session_code,
                    es.session_type,
                    es.status,
                    es.created_at,
                    es.updated_at,
                    eq.subject,
                    
                    -- Client info (for expert view)
                    CONCAT(cu.first_name, ' ', cu.last_name) AS client_name,
                    
                    -- Expert info
                    ep.id AS expert_id,
                    CONCAT(eu.first_name, ' ', eu.last_name) AS expert_name,
                    ep.specialization AS expert_specialization,
                    eu.profile_picture_url AS expert_picture,
                    ep.is_available AS expert_available,
                    
                    -- Last message
                    (SELECT message_content FROM expert_session_messages 
                     WHERE session_id = es.id 
                     ORDER BY created_at DESC LIMIT 1) AS last_message
                     
                FROM expert_sessions es
                LEFT JOIN expert_queries eq ON es.query_id = eq.id
                LEFT JOIN users cu ON es.user_id = cu.id
                LEFT JOIN expert_profiles ep ON es.expert_id = ep.id
                LEFT JOIN users eu ON ep.user_id = eu.id
                WHERE es.expert_id = :expert_profile_id
                AND es.expert_id IS NOT NULL
                AND ep.id IS NOT NULL
                ORDER BY es.updated_at DESC
            """)
            params = {"expert_profile_id": expert_profile_id}
        else:
            # Regular user sees their own sessions - ONLY with human experts
            query_sql = text("""
                SELECT 
                    es.id AS session_id,
                    es.session_code,
                    es.session_type,
                    es.status,
                    es.created_at,
                    es.updated_at,
                    eq.subject,
                    
                    -- Expert info
                    ep.id AS expert_id,
                    CONCAT(eu.first_name, ' ', eu.last_name) AS expert_name,
                    ep.specialization AS expert_specialization,
                    eu.profile_picture_url AS expert_picture,
                    ep.is_available AS expert_available,
                    
                    -- Last message
                    (SELECT message_content FROM expert_session_messages 
                     WHERE session_id = es.id 
                     ORDER BY created_at DESC LIMIT 1) AS last_message
                     
                FROM expert_sessions es
                LEFT JOIN expert_queries eq ON es.query_id = eq.id
                LEFT JOIN expert_profiles ep ON es.expert_id = ep.id
                LEFT JOIN users eu ON ep.user_id = eu.id
                WHERE es.user_id = :user_id
                AND es.expert_id IS NOT NULL
                AND ep.id IS NOT NULL
                ORDER BY es.updated_at DESC
            """)
            params = {"user_id": current_user.id}
        
        result = db.execute(query_sql, params)
        rows = result.fetchall()
        
        sessions = []
        for row in rows:
            if is_expert:
                # Expert view
                sessions.append({
                    "session_id": str(row[0]),
                    "session_code": row[1],
                    "session_type": row[2],
                    "status": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "updated_at": row[5].isoformat() if row[5] else None,
                    "subject": row[6],
                    "expert_name": row[7] or "Client",  # client_name in expert view
                    "expert_id": str(row[8]) if row[8] else None,
                    "expert_specialization": row[10] or "General",
                    "expert_picture": row[11],
                    "expert_available": bool(row[12]) if row[12] is not None else False,
                    "last_message": row[13] or "No messages yet",
                    "unread_count": 0  # Simplified - no unread tracking
                })
            else:
                # User view
                sessions.append({
                    "session_id": str(row[0]),
                    "session_code": row[1],
                    "session_type": row[2],
                    "status": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "updated_at": row[5].isoformat() if row[5] else None,
                    "subject": row[6],
                    "expert_id": str(row[7]) if row[7] else None,
                    "expert_name": row[8] or "Unassigned",
                    "expert_specialization": row[9] or "General",
                    "expert_picture": row[10],
                    "expert_available": bool(row[11]) if row[11] is not None else False,
                    "last_message": row[12] or "No messages yet",
                    "unread_count": 0  # Simplified - no unread tracking
                })
        
        return {
            "success": True,
            "sessions": sessions,
            "total_count": len(sessions),
            "is_expert": is_expert
        }
        
    except Exception as e:
        logger.error(f"Error loading consultations: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# GET SESSION DETAILS
# =====================================================
@router.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific session"""
    try:
        query_sql = text("""
            SELECT 
                es.id,
                es.session_code,
                es.session_type,
                es.status,
                es.created_at,
                es.updated_at,
                eq.subject,
                eq.question,
                
                -- Expert info
                ep.id AS expert_id,
                CONCAT(eu.first_name, ' ', eu.last_name) AS expert_name,
                ep.specialization AS expert_specialization,
                eu.profile_picture_url AS expert_picture,
                ep.is_available AS expert_available,
                
                -- Client info
                CONCAT(cu.first_name, ' ', cu.last_name) AS client_name
                
            FROM expert_sessions es
            LEFT JOIN expert_queries eq ON es.query_id = eq.id
            LEFT JOIN expert_profiles ep ON es.expert_id = ep.id
            LEFT JOIN users eu ON ep.user_id = eu.id
            LEFT JOIN users cu ON es.user_id = cu.id
            WHERE es.id = :session_id
            AND (es.user_id = :user_id OR ep.user_id = :user_id)
        """)
        
        result = db.execute(query_sql, {
            "session_id": session_id,
            "user_id": current_user.id
        })
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "success": True,
            "session_id": str(row[0]),
            "session_code": row[1],
            "session_type": row[2],
            "status": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
            "subject": row[6],
            "question": row[7],
            "expert_id": str(row[8]) if row[8] else None,
            "expert_name": row[9] or "Unassigned",
            "expert_specialization": row[10] or "General",
            "expert_picture": row[11],
            "expert_available": bool(row[12]) if row[12] is not None else False,
            "client_name": row[13]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# GET SESSION MESSAGES
# =====================================================
@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages for a session"""
    try:
        # Verify access - FIXED to handle NULL expert_id
        verify_sql = text("""
            SELECT es.user_id, ep.user_id AS expert_user_id
            FROM expert_sessions es
            LEFT JOIN expert_profiles ep ON es.expert_id = ep.id
            WHERE es.id = :session_id
        """)
        verify_result = db.execute(verify_sql, {"session_id": session_id})
        verify_row = verify_result.fetchone()
        
        if not verify_row:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if user is either the session creator or the assigned expert
        session_user_id = int(verify_row[0]) if verify_row[0] else None
        expert_user_id = int(verify_row[1]) if verify_row[1] else None
        current_user_id = int(current_user.id)
        
        has_access = (session_user_id == current_user_id or 
                     (expert_user_id is not None and expert_user_id == current_user_id))
        
        if not has_access:
            logger.warning(f"Access denied for user {current_user_id}. Session user: {session_user_id}, Expert user: {expert_user_id}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages - REMOVED is_read column
        messages_sql = text("""
            SELECT 
                esm.id,
                esm.session_id,
                esm.sender_id,
                CONCAT(u.first_name, ' ', u.last_name) AS sender_name,
                esm.sender_type,
                esm.message_content,
                esm.message_type,
                esm.created_at
            FROM expert_session_messages esm
            LEFT JOIN users u ON esm.sender_id = u.id
            WHERE esm.session_id = :session_id
            ORDER BY esm.created_at ASC
        """)
        
        result = db.execute(messages_sql, {"session_id": session_id})
        rows = result.fetchall()
        
        messages = []
        for row in rows:
            messages.append({
                "message_id": str(row[0]),
                "session_id": str(row[1]),
                "sender_id": str(row[2]),
                "sender_name": row[3],
                "sender_type": row[4],
                "message_content": row[5],
                "message_type": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "is_read": False  # Simplified
            })
        
        return {
            "success": True,
            "messages": messages,
            "total_count": len(messages)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# SEND MESSAGE
# =====================================================
@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in a session"""
    try:
        # Verify access - FIXED to handle NULL expert_id
        verify_sql = text("""
            SELECT es.user_id, ep.user_id AS expert_user_id
            FROM expert_sessions es
            LEFT JOIN expert_profiles ep ON es.expert_id = ep.id
            WHERE es.id = :session_id
        """)
        verify_result = db.execute(verify_sql, {"session_id": session_id})
        verify_row = verify_result.fetchone()
        
        if not verify_row:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if user is either the session creator or the assigned expert
        session_user_id = int(verify_row[0]) if verify_row[0] else None
        expert_user_id = int(verify_row[1]) if verify_row[1] else None
        current_user_id = int(current_user.id)
        
        has_access = (session_user_id == current_user_id or 
                     (expert_user_id is not None and expert_user_id == current_user_id))
        
        if not has_access:
            logger.warning(f"Access denied for user {current_user_id}. Session user: {session_user_id}, Expert user: {expert_user_id}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Determine sender type
        is_expert = verify_row[1] == current_user.id
        sender_type = "expert" if is_expert else "user"
        
        # Insert message - REMOVED is_read column
        message_id = str(uuid.uuid4())
        insert_sql = text("""
            INSERT INTO expert_session_messages (
                id, session_id, sender_id, sender_type,
                message_content, message_type, created_at
            ) VALUES (
                :id, :session_id, :sender_id, :sender_type,
                :message_content, :message_type, NOW()
            )
        """)
        
        db.execute(insert_sql, {
            "id": message_id,
            "session_id": session_id,
            "sender_id": current_user.id,
            "sender_type": sender_type,
            "message_content": message_data.message_content,
            "message_type": message_data.message_type
        })
        
        # Update session updated_at
        update_session_sql = text("""
            UPDATE expert_sessions 
            SET updated_at = NOW()
            WHERE id = :session_id
        """)
        db.execute(update_session_sql, {"session_id": session_id})
        
        db.commit()
        
        return {
            "success": True,
            "message_id": message_id,
            "created_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# CREATE SESSION (Start New Consultation)
# =====================================================

@router.post("/sessions")
async def create_session(
    session_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new consultation session"""
    try:
        # Generate IDs
        query_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        query_code = f"QRY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        session_code = f"SES-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Extract with defaults
        subject = session_data.get("subject", "Consultation Request")
        question = session_data.get("question", "")
        session_type = session_data.get("session_type", "text_chat")
        priority = session_data.get("priority", "normal")
        
        # Create query
        insert_query_sql = text("""
            INSERT INTO expert_queries (
                id, query_code, user_id, query_type,
                subject, question, priority, status,
                session_type, asked_at, created_at
            ) VALUES (
                :id, :query_code, :user_id, 'general',
                :subject, :question, :priority, 'open',
                :session_type, NOW(), NOW()
            )
        """)
        
        db.execute(insert_query_sql, {
            "id": query_id,
            "query_code": query_code,
            "user_id": current_user.id,
            "subject": subject,
            "question": question,
            "priority": priority,
            "session_type": session_type
        })
        
        # Create session - FIXED: start_time instead of started_at
        insert_session_sql = text("""
            INSERT INTO expert_sessions (
                id, session_code, query_id, user_id,
                session_type, status, start_time, created_at
            ) VALUES (
                :id, :session_code, :query_id, :user_id,
                :session_type, 'active', NOW(), NOW()
            )
        """)
        
        db.execute(insert_session_sql, {
            "id": session_id,
            "session_code": session_code,
            "query_id": query_id,
            "user_id": current_user.id,
            "session_type": session_type
        })
        
        db.commit()
        
        logger.info(f"✅ Session created: {session_code}")
        
        return {
            "success": True,
            "message": "Session created successfully",
            "session_id": session_id,
            "session_code": session_code,
            "query_id": query_id,
            "query_code": query_code,
            "status": "active"
        }
        
    except Exception as e:
        logger.error(f"❌ Error creating session: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )

# =====================================================
# END SESSION
# =====================================================
@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """End a consultation session"""
    try:
        # Verify access - FIXED to handle NULL expert_id
        verify_sql = text("""
            SELECT es.user_id, ep.user_id AS expert_user_id
            FROM expert_sessions es
            LEFT JOIN expert_profiles ep ON es.expert_id = ep.id
            WHERE es.id = :session_id
        """)
        verify_result = db.execute(verify_sql, {"session_id": session_id})
        verify_row = verify_result.fetchone()
        
        if not verify_row:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if user is either the session creator or the assigned expert
        session_user_id = int(verify_row[0]) if verify_row[0] else None
        expert_user_id = int(verify_row[1]) if verify_row[1] else None
        current_user_id = int(current_user.id)
        
        has_access = (session_user_id == current_user_id or 
                     (expert_user_id is not None and expert_user_id == current_user_id))
        
        if not has_access:
            logger.warning(f"Access denied for user {current_user_id}. Session user: {session_user_id}, Expert user: {expert_user_id}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update session
        update_sql = text("""
            UPDATE expert_sessions 
            SET status = 'completed',
                end_time = NOW(),
                updated_at = NOW()
            WHERE id = :session_id
        """)
        db.execute(update_sql, {"session_id": session_id})
        
        # Update query
        update_query_sql = text("""
            UPDATE expert_queries eq
            JOIN expert_sessions es ON eq.id = es.query_id
            SET eq.status = 'closed',
                eq.closed_at = NOW()
            WHERE es.id = :session_id
        """)
        db.execute(update_query_sql, {"session_id": session_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Session ended successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))