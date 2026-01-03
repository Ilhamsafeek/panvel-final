# =====================================================
# FILE: app/api/api_v1/auth/email_verification.py
# Email Verification Endpoint
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.database import get_db
from app.models.user import User
from app.core.email import send_welcome_email
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# =====================================================
# REQUEST SCHEMAS
# =====================================================

class EmailVerificationRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: str

# =====================================================
# VERIFY EMAIL ENDPOINT
# =====================================================

@router.post("/verify-email")
async def verify_email(
    request_data: EmailVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Verify user email using token from verification email
    """
    try:
        token = request_data.token.strip()
        logger.info(f"📧 Email verification attempt with token: {token[:20]}...")
        
        # Find user by verification token
        user = db.query(User).filter(
            User.email_verification_token == token
        ).first()
        
        if not user:
            logger.warning(f"⚠️ Invalid verification token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification link. Please request a new one."
            )
        
        # Check if already verified
        if user.is_verified:
            logger.info(f"ℹ️ User already verified: {user.email}")
            return {
                "success": True,
                "message": "Email already verified. You can log in now.",
                "redirect_url": "/login"
            }
        
        # Verify the user
        user.is_verified = True
        user.is_active = True
        user.email_verified_at = datetime.utcnow()
        user.email_verification_token = None  # Clear token (single-use)
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"✅ Email verified successfully for: {user.email}")
        
        # Send welcome email (optional)
        try:
            user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
            send_welcome_email(user.email, user_name)
        except Exception as email_error:
            logger.error(f"⚠️ Failed to send welcome email: {str(email_error)}")
        
        return {
            "success": True,
            "message": "Email verified successfully! You can now log in to your account.",
            "redirect_url": "/login"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Email verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during verification. Please try again."
        )

@router.post("/resend-verification")
async def resend_verification(
    request_data: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Resend verification email
    """
    try:
        from app.core.email import send_verification_email
        import secrets
        
        email = request_data.email.lower().strip()
        logger.info(f"📧 Resend verification requested for: {email}")
        
        user = db.query(User).filter(User.email == email).first()
        
        # Always return success to prevent email enumeration
        success_message = "If this email exists, a verification link has been sent."
        
        if user and not user.is_verified:
            # Generate new token
            new_token = secrets.token_urlsafe(32)
            user.email_verification_token = new_token
            db.commit()
            
            # Send email
            user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
            send_verification_email(user.email, user_name, new_token)
            
            logger.info(f"✅ Verification email resent to: {email}")
        
        return {
            "success": True,
            "message": success_message
        }
        
    except Exception as e:
        logger.error(f"❌ Resend verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )