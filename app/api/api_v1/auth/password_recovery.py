# =====================================================
# File: app/api/api_v1/auth/password_recovery.py
# Password Recovery API - Email-based reset process (UC003)
# FIXED: GET endpoint for validate-reset-token + security_question check
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr, validator
import secrets
import hashlib
import json
import logging
import re

from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# =====================================================
# PYDANTIC SCHEMAS
# =====================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    captcha: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    token: str
    newPassword: str
    confirmPassword: str
    securityAnswer: Optional[str] = None
    
    @validator('newPassword')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirmPassword')
    def passwords_match(cls, v, values):
        if 'newPassword' in values and v != values['newPassword']:
            raise ValueError('Passwords do not match')
        return v

class ValidateTokenRequest(BaseModel):
    token: str

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def generate_reset_token() -> str:
    """Generate a secure, cryptographically signed reset token"""
    random_bytes = secrets.token_bytes(32)
    timestamp = datetime.utcnow().isoformat().encode()
    token = hashlib.sha256(random_bytes + timestamp).hexdigest()
    return token

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def send_password_reset_email(email: str, reset_link: str, user_name: str):
    """Send password reset email to user"""
    try:
        logger.info(f"📧 Password Reset Email:")
        logger.info(f"   To: {email}")
        logger.info(f"   Name: {user_name}")
        logger.info(f"   Reset Link: {reset_link}")
        # TODO: Integrate with actual email service
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send password reset email: {str(e)}")
        return False

async def send_password_changed_confirmation(email: str, user_name: str):
    """Send confirmation email after successful password change"""
    try:
        logger.info(f"📧 Password Changed Confirmation:")
        logger.info(f"   To: {email}")
        logger.info(f"   Name: {user_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send confirmation email: {str(e)}")
        return False

def log_audit_event(db: Session, event_type: str, user_id: int, ip_address: str, details: str = None):
    """Log password reset events to audit log"""
    try:
        audit_query = text("""
            INSERT INTO audit_logs (user_id, contract_id, action_type, action_details, ip_address, created_at)
            VALUES (:user_id, NULL, :action_type, :action_details, :ip_address, NOW())
        """)
        db.execute(audit_query, {
            "user_id": user_id,
            "action_type": event_type,
            "action_details": json.dumps({"details": details, "entity_type": "user", "entity_id": str(user_id)}),
            "ip_address": ip_address
        })
        db.commit()
    except Exception as e:
        logger.warning(f"⚠️ Failed to log audit event: {str(e)}")

# =====================================================
# FORGOT PASSWORD ENDPOINT
# =====================================================

@router.post("/forgot-password")
async def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset - UC003 Step 1-4
    """
    try:
        client_ip = get_client_ip(request)
        email = request_data.email.lower().strip()
        
        logger.info(f"🔐 Password reset requested for: {email} from IP: {client_ip}")
        
        user = db.query(User).filter(User.email == email).first()
        
        success_message = "If this email exists in our system, a password reset link has been sent."
        
        if user:
            if not user.is_active:
                logger.warning(f"⚠️ Password reset attempted for inactive account: {email}")
                return {"success": True, "message": success_message}
            
            reset_token = generate_reset_token()
            token_expiry = datetime.utcnow() + timedelta(hours=24)
            
            user.password_reset_token = reset_token
            user.password_reset_expires = token_expiry
            db.commit()
            
            base_url = str(request.base_url).rstrip('/')
            reset_link = f"{base_url}/password-recovery?token={reset_token}"
            
            user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
            background_tasks.add_task(send_password_reset_email, email, reset_link, user_name)
            
            log_audit_event(
                db=db,
                event_type="password_reset_requested",
                user_id=user.id,
                ip_address=client_ip,
                details=f"Reset token generated, expires at {token_expiry.isoformat()}"
            )
            
            logger.info(f"✅ Password reset token generated for: {email}")
            
            # DEBUG MODE: Return reset link in response (remove in production!)
            return {
                "success": True,
                "message": success_message,
                # ⚠️ DEBUG ONLY - Remove these fields in production!
                "debug": {
                    "email": email,
                    "reset_link": reset_link,
                    "expires_at": token_expiry.isoformat(),
                    "user_name": user_name
                }
            }
        else:
            logger.info(f"ℹ️ Password reset requested for non-existent email: {email}")
        
        return {"success": True, "message": success_message}
        
    except Exception as e:
        logger.error(f"❌ Forgot password error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred processing your request. Please try again."
        )

# =====================================================
# VALIDATE TOKEN ENDPOINT - SUPPORTS BOTH GET AND POST
# =====================================================

@router.get("/validate-reset-token")
async def validate_reset_token_get(
    token: str = Query(..., description="Reset token from email link"),
    db: Session = Depends(get_db)
):
    """
    Validate reset token (GET method) - Called when page loads with token
    """
    return await _validate_token(token, db)

@router.post("/validate-reset-token")
async def validate_reset_token_post(
    request_data: ValidateTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Validate reset token (POST method)
    """
    return await _validate_token(request_data.token, db)

async def _validate_token(token: str, db: Session):
    """
    Internal token validation logic
    """
    try:
        token = token.strip()
        
        user = db.query(User).filter(User.password_reset_token == token).first()
        
        if not user:
            logger.warning(f"⚠️ Invalid reset token attempted")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset link. Please request a new one."
            )
        
        if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
            logger.warning(f"⚠️ Expired reset token for user: {user.email}")
            user.password_reset_token = None
            user.password_reset_expires = None
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link has expired. Please request a new one."
            )
        
        # Safely check for security_question (may not exist in model)
        has_security_question = False
        security_question = None
        try:
            security_question = getattr(user, 'security_question', None)
            has_security_question = bool(security_question)
        except:
            pass
        
        return {
            "success": True,
            "valid": True,
            "email": user.email,
            "hasSecurityQuestion": has_security_question,
            "securityQuestion": security_question if has_security_question else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token validation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )

# =====================================================
# RESET PASSWORD ENDPOINT
# =====================================================

@router.post("/reset-password")
async def reset_password(
    request_data: ResetPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Reset password with token - UC003 Steps 7-8
    """
    try:
        client_ip = get_client_ip(request)
        token = request_data.token.strip()
        
        user = db.query(User).filter(User.password_reset_token == token).first()
        
        if not user:
            logger.warning(f"⚠️ Password reset attempted with invalid token from IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset link. Please request a new one."
            )
        
        if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
            logger.warning(f"⚠️ Password reset with expired token for: {user.email}")
            user.password_reset_token = None
            user.password_reset_expires = None
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link has expired. Please request a new one."
            )
        
        # Safely check for security question (may not exist in model)
        has_security_question = False
        try:
            security_question = getattr(user, 'security_question', None)
            security_answer = getattr(user, 'security_answer', None)
            has_security_question = bool(security_question and security_answer)
        except:
            pass
        
        if has_security_question:
            if not request_data.securityAnswer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Security answer is required."
                )
            
            provided_answer = request_data.securityAnswer.strip().lower()
            stored_answer = security_answer.lower() if security_answer else ""
            
            if provided_answer != stored_answer:
                logger.warning(f"⚠️ Incorrect security answer for: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect security answer."
                )
        
        # Update password hash
        user.password_hash = hash_password(request_data.newPassword)
        
        # Clear reset token (single-use)
        user.password_reset_token = None
        user.password_reset_expires = None
        
        # Reset failed login attempts
        if hasattr(user, 'failed_login_attempts'):
            user.failed_login_attempts = 0
        if hasattr(user, 'account_locked_until'):
            user.account_locked_until = None
        
        # Update metadata
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Invalidate all active sessions
        try:
            invalidate_query = text("""
                UPDATE user_sessions 
                SET is_active = 0, last_activity = NOW()
                WHERE user_id = :user_id AND is_active = 1
            """)
            db.execute(invalidate_query, {"user_id": user.id})
            db.commit()
            logger.info(f"🔒 All sessions invalidated for user: {user.email}")
        except Exception as session_error:
            logger.warning(f"⚠️ Could not invalidate sessions: {str(session_error)}")
        
        # Send confirmation email
        user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
        background_tasks.add_task(send_password_changed_confirmation, user.email, user_name)
        
        # Log audit event
        log_audit_event(
            db=db,
            event_type="password_reset_success",
            user_id=user.id,
            ip_address=client_ip,
            details="Password successfully reset via email link"
        )
        
        logger.info(f"✅ Password successfully reset for: {user.email}")
        
        return {
            "success": True,
            "message": "Your password has been successfully reset. You can now login with your new password.",
            "redirect_url": "/login"
        }
        
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"❌ Password reset error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred resetting your password. Please try again."
        )

# =====================================================
# ADMIN FORCE RESET ENDPOINT
# =====================================================

@router.post("/admin/force-reset/{user_id}")
async def admin_force_password_reset(
    user_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Admin force password reset - UC003 Alternative Flow A3
    """
    try:
        client_ip = get_client_ip(request)
        
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        reset_token = generate_reset_token()
        token_expiry = datetime.utcnow() + timedelta(hours=24)
        
        user.password_reset_token = reset_token
        user.password_reset_expires = token_expiry
        db.commit()
        
        base_url = str(request.base_url).rstrip('/')
        reset_link = f"{base_url}/password-recovery?token={reset_token}"
        
        user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
        background_tasks.add_task(send_password_reset_email, user.email, reset_link, user_name)
        
        log_audit_event(
            db=db,
            event_type="admin_force_password_reset",
            user_id=user.id,
            ip_address=client_ip,
            details="Admin initiated password reset"
        )
        
        logger.info(f"✅ Admin force reset initiated for user: {user.email}")
        
        return {
            "success": True,
            "message": f"Password reset email sent to {user.email}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Admin force reset error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate password reset"
        )