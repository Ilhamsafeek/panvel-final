# =====================================================
# FILE: app/api/api_v1/auth/password_recovery.py
# UPDATED - ADD CAPTCHA FIELD
# =====================================================

from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.models.user import User
from app.core.security import hash_password
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import secrets
import string
from datetime import datetime, timedelta
import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# ROUTER INITIALIZATION
# =====================================================
router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"]
)

# =====================================================
# REQUEST/RESPONSE SCHEMAS - UPDATED WITH CAPTCHA
# =====================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="User's registered email address")
    captcha: Optional[str] = Field(None, description="CAPTCHA answer (validated client-side)")

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=100)
    newPassword: str = Field(..., min_length=8, max_length=128)
    confirmPassword: str = Field(..., min_length=8, max_length=128)
    securityAnswer: Optional[str] = Field(None, max_length=500)
    
    @validator('newPassword')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in string.punctuation for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirmPassword')
    def passwords_match(cls, v, values):
        if 'newPassword' in values and v != values['newPassword']:
            raise ValueError('Passwords do not match')
        return v

# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def get_client_ip(request: Request) -> str:
    """Extract client IP from request headers"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def generate_reset_token() -> str:
    """Generate cryptographically secure reset token"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))

# =====================================================
# EMAIL SENDING FUNCTION
# =====================================================
async def send_password_reset_email(email: str, reset_link: str, user_name: str):
    """Send password reset email using SMTP"""
    try:
        logger.info(f"📧 Starting email send process for: {email}")
        
        # SMTP Configuration
        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT
        smtp_user = settings.SMTP_USER
        smtp_password = settings.SMTP_PASSWORD
        from_email = settings.EMAILS_FROM_EMAIL
        
        logger.info(f"📬 SMTP Config: Host={smtp_host}, Port={smtp_port}, User={smtp_user}, From={from_email}")
        
        if not smtp_user or not smtp_password:
            logger.error("❌ SMTP credentials not configured")
            logger.info(f"🔗 Reset Link (for testing): {reset_link}")
            return False
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = " Password Reset Request - CALIM 360"
        msg['From'] = f"CALIM 360 <{from_email}>"
        msg['To'] = email
        
        logger.info(f"📝 Email message created. Subject: {msg['Subject']}")
        
        # HTML Email Body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #1a5f7a 0%, #2762cb 100%); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .content {{ padding: 40px 30px; }}
                .button {{ display: inline-block; padding: 16px 40px; background: linear-gradient(135deg, #1a5f7a 0%, #2762cb 100%); color: white !important; text-decoration: none; border-radius: 8px; font-weight: 600; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div style="font-size: 48px; margin-bottom: 10px;"></div>
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <h2 style="color: #1a5f7a;">Hello {user_name},</h2>
                    <p>We received a request to reset your password for your CALIM 360 account.</p>
                    <p>Click the button below to create a new password. This link will expire in <strong>24 hours</strong>.</p>
                    <div style="text-align: center; margin: 35px 0;">
                        <a href="{reset_link}" class="button">Reset Your Password</a>
                    </div>
                    <p style="font-size: 14px; color: #666;">If the button doesn't work, copy and paste this link:</p>
                    <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; word-break: break-all; font-family: monospace; font-size: 14px;">{reset_link}</div>
                    <div style="background: #fff3cd; border-left: 4px solid #f0ad4e; padding: 15px; margin: 25px 0; border-radius: 6px;">
                        <strong style="color: #856404;">⚠️ Security Notice:</strong>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">If you didn't request this, please ignore this email or contact support.</p>
                    </div>
                </div>
                <div class="footer">
                    <p><strong>CALIM 360</strong> - Smart Contract Lifecycle Management</p>
                    <p>© {datetime.now().year} CALIM 360. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Password Reset Request - CALIM 360

Hello {user_name},

We received a request to reset your password.

Reset your password (expires in 24 hours):
{reset_link}

If you didn't request this, please ignore this email.

---
CALIM 360 - Smart Contract Lifecycle Management
© {datetime.now().year} CALIM 360. All rights reserved.
        """
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        logger.info(f"📎 Email body attached (HTML + Plain text)")
        
        # Send email
        logger.info(f"🔌 Connecting to SMTP server: {smtp_host}:{smtp_port}")
        
        if smtp_port == 465:
            logger.info(" Using SSL connection (port 465)")
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                logger.info("🔑 Logging in to SMTP server...")
                server.login(smtp_user, smtp_password)
                logger.info("📤 Sending email...")
                server.send_message(msg)
                logger.info(" Email sent via SSL")
        else:
            logger.info(" Using TLS connection (port 587)")
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                logger.info("🔑 Logging in to SMTP server...")
                server.login(smtp_user, smtp_password)
                logger.info("📤 Sending email...")
                server.send_message(msg)
                logger.info(" Email sent via TLS")
        
        logger.info(f" Password reset email successfully sent to: {email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ SMTP Authentication Failed: {str(e)}")
        logger.error(f"   Username: {smtp_user}")
        logger.error(f"   Server: {smtp_host}:{smtp_port}")
        logger.error("   Please verify SMTP credentials in .env file")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP Error: {str(e)}")
        logger.error(f"   Server: {smtp_host}:{smtp_port}")
        return False
    except Exception as e:
        logger.error(f"❌ Email sending failed with error: {str(e)}", exc_info=True)
        return False
        

async def send_password_changed_confirmation(email: str, user_name: str):
    """Send confirmation email after password change"""
    try:
        logger.info(f"📧 Sending password changed confirmation to: {email}")
        
        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT
        smtp_user = settings.SMTP_USER
        smtp_password = settings.SMTP_PASSWORD
        from_email = settings.EMAILS_FROM_EMAIL
        
        if not smtp_user or not smtp_password:
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = " Password Changed Successfully - CALIM 360"
        msg['From'] = f"CALIM 360 <{from_email}>"
        msg['To'] = email
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 20px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 40px 30px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 10px;"></div>
                    <h1 style="margin: 0;">Password Changed Successfully</h1>
                </div>
                <div style="padding: 40px 30px;">
                    <h2 style="color: #28a745;">Hello {user_name},</h2>
                    <p>Your CALIM 360 password has been successfully changed.</p>
                    <p><strong>Change Details:</strong></p>
                    <ul>
                        <li>Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</li>
                        <li>Account: {email}</li>
                    </ul>
                    <div style="background: #fff3cd; border-left: 4px solid #f0ad4e; padding: 15px; margin: 20px 0; border-radius: 6px;">
                        <strong style="color: #856404;"> Security Notice:</strong>
                        <p style="margin: 5px 0 0 0;">If you didn't make this change, contact support immediately.</p>
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 14px;">
                    <p><strong>CALIM 360</strong></p>
                    <p>© {datetime.now().year} CALIM 360. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        
        logger.info(f" Password changed confirmation sent to: {email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Confirmation email failed: {str(e)}")
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
        logger.warning(f"⚠️ Audit logging failed: {str(e)}")

# =====================================================
# API ENDPOINTS
# =====================================================

@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset - UC003 Step 1-4
    Accepts raw JSON to avoid validation issues
    """
    try:
        # Parse request body manually
        body = await request.json()
        logger.info(f"📦 Received request body: {body}")
        
        # Clean email: lowercase, strip whitespace AND trailing periods/commas
        email = body.get('email', '').lower().strip().rstrip('.,;')
        captcha = body.get('captcha', '')
        
        logger.info(f"🧹 Cleaned email: {email}")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is required"
            )
        
        # Validate email format
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        client_ip = get_client_ip(request)
        logger.info(f" Password reset requested for: {email} from IP: {client_ip}")
        
        user = db.query(User).filter(User.email == email).first()
        
        success_message = "If this email exists in our system, a password reset link has been sent."
        
        if user:
            # Check if account is active
            if not user.is_active:
                logger.warning(f"⚠️ Password reset attempted for INACTIVE account: {email}")
                return {
                    "success": False,
                    "message": "This account is inactive. Please contact support for assistance."
                }
            
            # Check if email is verified
            if hasattr(user, 'is_verified') and not user.is_verified:
                logger.warning(f"⚠️ Password reset attempted for UNVERIFIED account: {email}")
                return {
                    "success": False,
                    "message": "Please verify your email address first. Check your inbox for the verification link."
                }
            
            # Generate reset token
            reset_token = generate_reset_token()
            token_expiry = datetime.utcnow() + timedelta(hours=24)
            
            # Save token to database
            user.password_reset_token = reset_token
            user.password_reset_expires = token_expiry
            db.commit()
            
            # Build reset link
            base_url = str(request.base_url).rstrip('/')
            reset_link = f"{base_url}/password-recovery?token={reset_token}"
            
            # Get user name
            user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
            
            # Send email in background
            background_tasks.add_task(send_password_reset_email, email, reset_link, user_name)
            
            # Log audit event
            log_audit_event(
                db=db,
                event_type="password_reset_requested",
                user_id=user.id,
                ip_address=client_ip,
                details=f"Reset token generated, expires at {token_expiry.isoformat()}"
            )
            
            logger.info(f" Password reset token generated for: {email}")
            logger.info(f"🔗 Reset link: {reset_link}")
            
            return {
                "success": True,
                "message": success_message
            }
        else:
            logger.info(f"ℹ️ Password reset requested for non-existent email: {email}")
        
        return {"success": True, "message": success_message}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Forgot password error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred processing your request. Please try again."
        )


@router.post("/reset-password")
async def reset_password(
    request_data: ResetPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Reset password using token - UC003 Step 5-8"""
    try:
        client_ip = get_client_ip(request)
        
        user = db.query(User).filter(
            User.password_reset_token == request_data.token
        ).first()
        
        if not user:
            logger.warning(f"⚠️ Invalid reset token from IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset link. Please request a new one."
            )
        
        if not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
            logger.warning(f"⚠️ Expired reset token for: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link has expired. Please request a new one."
            )
        
        user.password_hash = hash_password(request_data.newPassword)
        user.password_reset_token = None
        user.password_reset_expires = None
        
        if hasattr(user, 'failed_login_attempts'):
            user.failed_login_attempts = 0
        if hasattr(user, 'account_locked_until'):
            user.account_locked_until = None
        
        user.updated_at = datetime.utcnow()
        db.commit()
        
        try:
            invalidate_query = text("""
                UPDATE user_sessions 
                SET is_active = 0, last_activity = NOW()
                WHERE user_id = :user_id AND is_active = 1
            """)
            db.execute(invalidate_query, {"user_id": user.id})
            db.commit()
            logger.info(f" All sessions invalidated for user: {user.email}")
        except Exception as session_error:
            logger.warning(f"⚠️ Could not invalidate sessions: {str(session_error)}")
        
        user_name = f"{user.first_name} {user.last_name}" if user.first_name else "User"
        background_tasks.add_task(send_password_changed_confirmation, user.email, user_name)
        
        log_audit_event(
            db=db,
            event_type="password_reset_success",
            user_id=user.id,
            ip_address=client_ip,
            details="Password successfully reset via email link"
        )
        
        logger.info(f" Password successfully reset for: {user.email}")
        
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