# =====================================================
# FILE: app/api/api_v1/chatbot/routes.py
# Chatbot API Routes with Claude AI Integration
# Updated to use chatbot_claude_service
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.consultation import ExpertSessionMessage, ExpertSession

# Import the chatbot-specific Claude service
from app.services.chatbot_claude_service import chatbot_claude_service

from app.api.api_v1.chatbot.schemas import (
    ChatQueryRequest,
    ChatQueryResponse,
    ConversationHistoryResponse,
    ChatSessionCreate,
    ChatSessionResponse
)

router = APIRouter(prefix="/api/v1/chatbot", tags=["chatbot"])
logger = logging.getLogger(__name__)


@router.post("/query", response_model=ChatQueryResponse)
async def process_chatbot_query(
    request: ChatQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process a chatbot query and return AI-generated response
    
    - **query**: User's question or message (required)
    - **tone**: Response tone - formal, friendly, technical, etc. (default: formal)
    - **language**: Response language - en or ar (default: en)
    - **contract_id**: Optional contract ID for context-aware responses
    - **session_id**: Optional session ID for conversation continuity
    
    Returns:
    - Primary AI response with confidence score
    - 3 response variants (detailed, concise, action-oriented)
    - Clause references (if contract context provided)
    - Processing metadata (tokens used, time taken)
    """
    try:
        logger.info(f"Processing chatbot query from user {current_user.id}: {request.query[:50]}...")
        
        # Get conversation history if session_id provided
        conversation_history = []
        if request.session_id:
            history_messages = db.query(ExpertSessionMessage).filter(
                ExpertSessionMessage.session_id == request.session_id
            ).order_by(ExpertSessionMessage.created_at.desc()).limit(10).all()
            
            # Build conversation history in correct format
            for msg in reversed(history_messages):
                conversation_history.append({
                    "role": "assistant" if msg.sender_type == "system" else "user",
                    "content": msg.message_content,
                    "sender_type": msg.sender_type,
                    "message_content": msg.message_content
                })
            
            logger.info(f"Loaded {len(conversation_history)} previous messages for context")
        
        # Get contract context if contract_id provided
        contract_context = None
        if request.contract_id:
            contract_context = _get_contract_context(db, request.contract_id)
            logger.info(f"Contract context loaded: {contract_context.get('contract_number', 'N/A')}")
        
        # Generate AI response using chatbot Claude service
        ai_response = await chatbot_claude_service.generate_chat_response(
            user_message=request.query,
            conversation_history=conversation_history,
            tone=request.tone,
            language=request.language,
            contract_context=contract_context,
            user_role=current_user.user_type
        )
        
        if not ai_response.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ai_response.get("error", "Failed to generate response")
            )
        
        # Save conversation to database if session exists
        if request.session_id:
            try:
                # Save user message
                user_msg = ExpertSessionMessage(
                    session_id=request.session_id,
                    sender_id=current_user.id,
                    sender_type="user",
                    message_type="text",
                    message_content=request.query,
                    is_ai_generated=False
                )
                db.add(user_msg)
                
                # Save AI response
                ai_msg = ExpertSessionMessage(
                    session_id=request.session_id,
                    sender_id=current_user.id,
                    sender_type="system",
                    message_type="text",
                    message_content=ai_response["primary_response"],
                    is_ai_generated=True,
                    ai_confidence=ai_response.get("confidence_score", 0.9)
                )
                db.add(ai_msg)
                db.commit()
                
                logger.info(f"✅ Messages saved to database for session {request.session_id}")
            except Exception as e:
                logger.error(f"Failed to save messages to database: {e}")
                db.rollback()
                # Continue anyway - don't fail the request
        
        # Build response
        response = ChatQueryResponse(
            success=True,
            message="Response generated successfully",
            response=ai_response["primary_response"],
            variants=ai_response.get("variants", []),
            clause_references=ai_response.get("clause_references", []),
            confidence_score=ai_response.get("confidence_score", 0.95),
            session_id=request.session_id,
            timestamp=datetime.utcnow(),
            tokens_used=ai_response.get("tokens_used", 0),
            processing_time_ms=ai_response.get("processing_time_ms", 0)
        )
        
        logger.info(f"✅ Chatbot response completed in {ai_response.get('processing_time_ms', 0)}ms")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chatbot query error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    request: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new chatbot conversation session
    
    - Generates unique session code
    - Links to contract if contract_id provided
    - Sends welcome message
    - Stores in expert_sessions table
    """
    try:
        # Generate unique session code
        session_code = f"CHAT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{current_user.id}"
        
        logger.info(f"Creating chat session for user {current_user.id}: {session_code}")
        
        # Create session in database - REMOVED 'subject' field
        session = ExpertSession(
            session_code=session_code,
            user_id=current_user.id,
            session_type="ai_chatbot",
            status="active",
            contract_id=request.contract_id,
            query_text=request.subject or "AI Chatbot Consultation"  # ✅ Use query_text instead
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Add welcome message
        welcome_text = f"""👋 Hello {current_user.first_name}! I'm your CALIM360 AI Assistant.

I'm here to help you with:
- Contract questions and analysis
- Risk assessment and compliance
- Workflow and approval guidance
- CLM system features
- Legal and contractual guidance

How can I assist you today?"""
        
        welcome_message = ExpertSessionMessage(
            session_id=session.id,
            sender_id=current_user.id,
            sender_type="system",
            message_type="text",
            message_content=welcome_text,
            is_ai_generated=True,
            ai_confidence=1.0
        )
        
        db.add(welcome_message)
        db.commit()
        
        logger.info(f"✅ Chat session created: {session.id}")
        
        return ChatSessionResponse(
            success=True,
            session_id=session.id,
            session_code=session.session_code,
            message="Chat session created successfully",
            welcome_message=welcome_text
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Session creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )

        

@router.get("/sessions/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    session_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve conversation history for a chat session
    
    - Returns all messages in chronological order
    - Includes user and AI messages
    - Shows confidence scores for AI responses
    - Limited to specified number of messages
    """
    try:
        # Verify session belongs to user
        session = db.query(ExpertSession).filter(
            ExpertSession.id == session_id,
            ExpertSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied"
            )
        
        # Get messages
        messages = db.query(ExpertSessionMessage).filter(
            ExpertSessionMessage.session_id == session_id
        ).order_by(ExpertSessionMessage.created_at).limit(limit).all()
        
        # Format messages for response
        message_list = []
        for msg in messages:
            message_list.append({
                "id": msg.id,
                "sender_type": msg.sender_type,
                "message_content": msg.message_content,
                "message_type": msg.message_type,
                "is_ai_generated": msg.is_ai_generated,
                "confidence": msg.ai_confidence,
                "created_at": msg.created_at.isoformat()
            })
        
        logger.info(f"Retrieved {len(message_list)} messages for session {session_id}")
        
        return ConversationHistoryResponse(
            success=True,
            session_id=session_id,
            messages=message_list,
            total_messages=len(message_list)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ History retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}"
        )


@router.post("/escalate")
async def escalate_to_expert(
    session_id: str,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Escalate chatbot conversation to human expert (UC-035)
    
    - Changes session type from ai_chatbot to expert_consultation
    - Updates session status to 'escalated'
    - Logs escalation reason
    - Triggers expert notification (to be implemented)
    """
    try:
        session = db.query(ExpertSession).filter(
            ExpertSession.id == session_id,
            ExpertSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Update session to escalated status
        session.status = "escalated"
        session.session_type = "expert_consultation"
        
        # Add escalation message
        escalation_msg = ExpertSessionMessage(
            session_id=session_id,
            sender_id=current_user.id,
            sender_type="system",
            message_type="system",
            message_content=f"""🔄 **Conversation Escalated to Human Expert**

**Reason:** {reason}

A qualified legal expert will be assigned to your case shortly. You will receive a notification when an expert joins the consultation.

**What happens next:**
1. Your request has been prioritized based on urgency
2. An expert will review your conversation history
3. You'll receive expert guidance within the expected timeframe
4. All previous chat context is preserved

Thank you for your patience.""",
            is_ai_generated=False
        )
        db.add(escalation_msg)
        db.commit()
        
        logger.info(f"✅ Session {session_id} escalated to expert. Reason: {reason}")
        
        # TODO: Trigger expert notification system
        # - Send email/SMS to available experts
        # - Create task in expert queue
        # - Update dashboard notifications
        
        return {
            "success": True,
            "message": "Session escalated to expert successfully",
            "session_id": session_id,
            "new_status": "escalated",
            "notification": "You will be notified when an expert is assigned"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Escalation error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to escalate session: {str(e)}"
        )


@router.get("/config")
async def get_chatbot_config():
    """
    Get chatbot configuration and available options
    
    Returns:
    - Available tones
    - Supported languages
    - Quick action suggestions
    - System capabilities
    """
    return {
        "success": True,
        "config": {
            "available_tones": [
                {"value": "formal", "label": "Formal", "icon": "ti-tie"},
                {"value": "conciliatory", "label": "Conciliatory", "icon": "ti-handshake"},
                {"value": "friendly", "label": "Friendly", "icon": "ti-mood-smile"},
                {"value": "assertive", "label": "Assertive", "icon": "ti-bolt"},
                {"value": "analytical", "label": "Analytical", "icon": "ti-chart-line"},
                {"value": "empathetic", "label": "Empathetic", "icon": "ti-heart"},
                {"value": "consultative", "label": "Consultative", "icon": "ti-user-check"},
                {"value": "instructive", "label": "Instructive", "icon": "ti-school"},
                {"value": "neutral", "label": "Neutral", "icon": "ti-equal"},
                {"value": "persuasive", "label": "Persuasive", "icon": "ti-speakerphone"},
                {"value": "technical", "label": "Technical", "icon": "ti-code"},
                {"value": "simplified", "label": "Simplified", "icon": "ti-bulb"}
            ],
            "available_languages": [
                {"code": "en", "name": "English", "icon": "🇬🇧"},
                {"code": "ar", "name": "Arabic", "icon": "🇶🇦"}
            ],
            "quick_actions": [
                {
                    "id": "risk_analysis",
                    "label": "Analyze Contract Risk",
                    "query": "Can you analyze the risks in this contract?",
                    "icon": "ti-alert-triangle"
                },
                {
                    "id": "clause_help",
                    "label": "Explain a Clause",
                    "query": "Can you explain what this clause means?",
                    "icon": "ti-file-text"
                },
                {
                    "id": "workflow_help",
                    "label": "Workflow Guidance",
                    "query": "How do I set up an approval workflow?",
                    "icon": "ti-git-merge"
                },
                {
                    "id": "compliance",
                    "label": "Check Compliance",
                    "query": "Is this compliant with Qatar regulations?",
                    "icon": "ti-shield-check"
                }
            ],
            "capabilities": [
                "Contract drafting assistance",
                "Risk analysis",
                "Clause interpretation",
                "Workflow guidance",
                "Compliance checking",
                "Negotiation strategies",
                "Document analysis",
                "Expert escalation"
            ],
            "max_message_length": 5000,
            "support_file_upload": True,
            "ai_model": chatbot_claude_service.model,
            "ai_enabled": chatbot_claude_service.client is not None
        }
    }


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def _get_contract_context(db: Session, contract_id: str) -> dict:
    """
    Helper function to get contract context for AI
    
    TODO: Implement actual contract retrieval from database
    For now returns mock data structure
    """
    
    # This is a placeholder - implement with actual Contract model
    # from app.models.contract import Contract
    # contract = db.query(Contract).filter(Contract.id == contract_id).first()
    
    return {
        "contract_id": contract_id,
        "contract_type": "Master Service Agreement",
        "contract_number": "MSA-2025-001",
        "status": "draft",
        "parties": ["Company A", "Company B"],
        "value": "QAR 500,000",
        "clauses": [
            {
                "id": "clause-1",
                "clause_number": "1.1",
                "title": "Definitions",
                "section": "Preliminary",
                "content": "In this Agreement, unless the context otherwise requires: 'Services' means..."
            },
            {
                "id": "clause-2",
                "clause_number": "5.1",
                "title": "Confidentiality",
                "section": "Obligations",
                "content": "Both parties agree to maintain strict confidentiality..."
            },
            {
                "id": "clause-3",
                "clause_number": "8.1",
                "title": "Termination",
                "section": "Duration and Termination",
                "content": "Either party may terminate this Agreement by giving..."
            }
        ]
    }