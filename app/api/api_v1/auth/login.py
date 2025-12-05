# =====================================================
# File: app/api/api_v1/auth/login.py
# Fixed Login Backend with Session Cookie Support
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import secrets
import logging

from app.core.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.api.api_v1.auth.schemas import (
    LoginRequest,
    LoginResponse,
    TwoFactorVerifyRequest,
    SecurityQuestionVerifyRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# =====================================================
# LOGIN ENDPOINT - FIXED WITH SESSION COOKIE
# =====================================================
@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User login with password validation, account lockout, and 2FA support
    NOW SETS SESSION COOKIE FOR WEB AUTHENTICATION
    
    Business Rules:
    - Max 5 failed attempts before 30-minute lockout
    - Session expires after 30 minutes of inactivity
    - 2FA required if enabled for user
    - Logs IP and device info for security
    - Sets session cookie for web-based authentication
    """
    try:
        logger.info(f"Login attempt for: {login_data.email}")
        
        # Get user by email
        user = db.query(User).filter(User.email == login_data.email.lower()).first()
        
        if not user:
            logger.warning(f"User not found: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if account is locked
        if user.account_locked_until and user.account_locked_until > datetime.utcnow():
            time_remaining = (user.account_locked_until - datetime.utcnow()).seconds // 60
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked. Try again in {time_remaining} minutes."
            )
        
        # Check if account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active. Please contact administrator."
            )
        
        # Verify password
        if not verify_password(login_data.password, user.password_hash):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            if user.failed_login_attempts >= 5:
                # Lock account for 30 minutes
                user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
                db.commit()
                logger.warning(f"Account locked for user: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Too many failed attempts. Account locked for 30 minutes."
                )
            
            db.commit()
            attempts_remaining = 5 - user.failed_login_attempts
            logger.warning(f"Failed login attempt for: {user.email}, {attempts_remaining} attempts remaining")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid email or password. {attempts_remaining} attempts remaining."
            )
        
        # Password is correct - reset failed attempts
        user.failed_login_attempts = 0
        user.account_locked_until = None
        
        # Get client IP address
        client_ip = request.client.host if request.client else "unknown"
        
        # Check for 2FA requirement
        if user.two_factor_enabled:
            # Generate and store OTP (6-digit code)
            otp_code = str(secrets.randbelow(1000000)).zfill(6)
            otp_expires = datetime.utcnow() + timedelta(minutes=5)
            
            # Store OTP temporarily (in production, use Redis or temp table)
            # For now, we'll log it
            logger.info(f"🔐 2FA OTP for {user.email}: {otp_code} (expires in 5 minutes)")
            
            # TODO: Send OTP via SMS/Email based on user preference
            # await send_otp_email(user.email, user.first_name, otp_code)
            
            # Update last login attempt
            user.last_login_ip = client_ip
            db.commit()
            
            return LoginResponse(
                success=True,
                message="2FA required. Please enter the OTP sent to your device.",
                requires_2fa=True,
                requires_security_question=False,
                user=None,
                access_token=None
            )
        
        # Check for suspicious activity (new IP)
        # If last_login_ip is different and exists, trigger security question
        # For simplicity, we'll skip this for now
        
        # Generate JWT token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "user_type": user.user_type
            }
        )
        
        # 🔧 FIX: Set session cookie for web authentication
        response.set_cookie(
            key="session_token",
            value=access_token,
            max_age=1800,  # 30 minutes
            httponly=True,  # Prevent XSS attacks
            secure=False,   # Set to True in production with HTTPS
            samesite="lax"  # CSRF protection
        )
        
        # Update last login info
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = client_ip
        db.commit()
        
        logger.info(f"✅ Successful login for: {user.email} - Session cookie set")
        
        return LoginResponse(
            success=True,
            message="Login successful!",
            requires_2fa=False,
            requires_security_question=False,
            user={
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_type": user.user_type,
                "company_id": user.company_id
            },
            access_token=access_token,
            redirect_url="/dashboard"  # Changed to dashboard
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )

# =====================================================
# 2FA VERIFICATION ENDPOINT
# =====================================================
@router.post("/verify-2fa", response_model=LoginResponse)
async def verify_2fa(
    verify_data: TwoFactorVerifyRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Verify 2FA OTP and complete login
    """
    try:
        user = db.query(User).filter(User.email == verify_data.email.lower()).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # TODO: Verify OTP from cache/database
        # For now, accept any 6-digit code for testing
        if len(verify_data.otp_code) != 6 or not verify_data.otp_code.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP format"
            )
        
        # Generate JWT token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "user_type": user.user_type
            }
        )
        
        # Set session cookie
        response.set_cookie(
            key="session_token",
            value=access_token,
            max_age=1800,
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        logger.info(f"✅ 2FA verification successful for: {user.email}")
        
        return LoginResponse(
            success=True,
            message="2FA verification successful!",
            requires_2fa=False,
            requires_security_question=False,
            user={
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_type": user.user_type,
                "company_id": user.company_id
            },
            access_token=access_token,
            redirect_url="/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="2FA verification failed"
        )

# =====================================================
# SECURITY QUESTION VERIFICATION ENDPOINT
# =====================================================
@router.post("/verify-security-question", response_model=LoginResponse)
async def verify_security_question(
    verify_data: SecurityQuestionVerifyRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Verify security question and complete login
    """
    try:
        user = db.query(User).filter(User.email == verify_data.email.lower()).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # TODO: Verify security question answer
        # For now, accept any non-empty answer for testing
        if not verify_data.answer or len(verify_data.answer.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security answer is too short"
            )
        
        # Generate JWT token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "user_type": user.user_type
            }
        )
        
        # Set session cookie
        response.set_cookie(
            key="session_token",
            value=access_token,
            max_age=1800,
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        logger.info(f"✅ Security question verification successful for: {user.email}")
        
        return LoginResponse(
            success=True,
            message="Security verification successful!",
            requires_2fa=False,
            requires_security_question=False,
            user={
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_type": user.user_type,
                "company_id": user.company_id
            },
            access_token=access_token,
            redirect_url="/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Security question verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security verification failed"
        )

# @router.get("/fix-current-user/{user_id}/{company_id}")
# async def fix_current_user(user_id: str, company_id: str, db: Session = Depends(get_db)):
#     from sqlalchemy import text
#     try:
#         # Create company
#         db.execute(text(f"""
#             INSERT INTO companies (id, company_name, cr_number, company_type, registration_status, license_type, is_active, created_at, updated_at)
#             VALUES ('{company_id}', 'Company {company_id}', 'CR-{company_id}', 'client', 'active', 'corporate', 1, NOW(), NOW())
#             ON DUPLICATE KEY UPDATE company_name = company_name
#         """))
        
#         # Create user
#         db.execute(text(f"""
#             INSERT INTO users (id, company_id, username, email, password_hash, first_name, last_name, user_type, is_active, email_verified, terms_accepted, privacy_accepted, created_at, updated_at)
#             VALUES ('{user_id}', '{company_id}', 'user{user_id}', 'user{user_id}@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lXvqc3WoNx3O', 'User', '{user_id}', 'client', 1, 1, 1, 1, NOW(), NOW())
#             ON DUPLICATE KEY UPDATE email = email
#         """))
#         db.commit()
        
#         verify = db.execute(text(f"SELECT id FROM users WHERE id = '{user_id}'")).fetchone()
#         return {"success": verify is not None, "message": f"User {user_id} ready!"}
#     except Exception as e:
#         db.rollback()
#         return {"error": str(e)}

# @router.get("/create-user-now")
# async def create_user_now(db: Session = Depends(get_db)):
#     from sqlalchemy import text
#     try:
#         # Create company 3
#         db.execute(text("""
#             INSERT INTO companies (id, company_name, cr_number, company_type, registration_status, license_type, is_active, created_at, updated_at)
#             VALUES (3, 'Company 3', 'CR-003', 'client', 'active', 'corporate', 1, NOW(), NOW())
#             ON DUPLICATE KEY UPDATE id=id
#         """))
        
#         # Create user 1
#         db.execute(text("""
#             INSERT INTO users (id, company_id, username, email, password_hash, first_name, last_name, user_type, is_active, email_verified, terms_accepted, privacy_accepted, created_at, updated_at)
#             VALUES (1, 3, 'faris', 'fr.faris2001@gmail.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lXvqc3WoNx3O', 'Faris', 'User', 'client', 1, 1, 1, 1, NOW(), NOW())
#             ON DUPLICATE KEY UPDATE id=id
#         """))
#         db.commit()
        
#         # Verify
#         check = db.execute(text("SELECT id, email FROM users WHERE id = 1")).fetchone()
#         return {"success": check is not None, "user": dict(zip(["id", "email"], check)) if check else None}
#     except Exception as e:
#         db.rollback()
#         return {"error": str(e)}
