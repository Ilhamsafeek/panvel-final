# =====================================================
# FILE: app/core/email.py
# Email Utilities for CALIM 360 - Complete SMTP Implementation
# Handles all email notifications using direct SMTP
# =====================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# HELPER FUNCTION - SEND EMAIL
# =====================================================

def send_email_smtp(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str = None
) -> bool:
    """
    Generic SMTP email sender
    Returns True if successful, False otherwise
    """
    try:
        # SMTP Configuration
        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT
        smtp_user = settings.SMTP_USER
        smtp_password = settings.SMTP_PASSWORD
        from_email = settings.EMAILS_FROM_EMAIL
        
        if not smtp_user or not smtp_password:
            logger.error("❌ SMTP credentials not configured in .env")
            return False
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"CALIM 360 <{from_email}>"
        msg['To'] = to_email
        
        # Attach text and HTML versions
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        if smtp_port == 465:
            # SSL connection
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            # TLS connection (port 587)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        
        logger.info(f" Email sent successfully to: {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ SMTP Authentication Failed: {str(e)}")
        logger.error(f"   Server: {smtp_host}:{smtp_port}, User: {smtp_user}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP Error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Email sending failed: {str(e)}", exc_info=True)
        return False


def send_welcome_email_with_credentials(
    email: str, 
    first_name: str, 
    last_name: str,
    password: str, 
    user_role: str = "User"
) -> bool:
    """
    Send welcome email with login credentials to new user
    """
    try:
        logger.info(f"📧 Sending welcome email with credentials to: {email}")
        
        user_full_name = f"{first_name} {last_name}"
        subject = "🎉 Welcome to CALIM 360 - Your Account is Ready!"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 30px auto; background: white; border-radius: 12px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #1a5f7a, #159895); padding: 40px; text-align: center; color: white; }}
                .content {{ padding: 40px 30px; }}
                .credentials {{ background: #f8f9fa; border-left: 4px solid #159895; padding: 20px; margin: 20px 0; }}
                .cred-row {{ margin: 10px 0; padding: 10px; background: white; border-radius: 4px; }}
                .label {{ font-weight: bold; color: #666; }}
                .value {{ font-family: monospace; background: #e9ecef; padding: 5px 10px; border-radius: 4px; }}
                .button {{ display: inline-block; background: #159895; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to CALIM 360</h1>
                </div>
                <div class="content">
                    <h2 style="color: #1a5f7a;">Hello {user_full_name}!</h2>
                    <p>Your account has been successfully created.</p>
                    
                    <div class="credentials">
                        <h3 style="margin-top: 0;">🔐 Your Login Credentials</h3>
                        <div class="cred-row">
                            <span class="label">Email:</span> <span class="value">{email}</span>
                        </div>
                        <div class="cred-row">
                            <span class="label">Password:</span> <span class="value">{password}</span>
                        </div>
                        <div class="cred-row">
                            <span class="label">Role:</span> <span class="value">{user_role}</span>
                        </div>
                    </div>
                    
                    <div class="warning">
                        <strong>🔒 Security Notice:</strong> Please change your password immediately after first login.
                    </div>
                    
                    <center>
                        <a href="https://calim360.com/login" class="button">Login Now →</a>
                    </center>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Welcome to CALIM 360!

Hello {user_full_name},

Your login credentials:
Email: {email}
Password: {password}
Role: {user_role}

Login: https://calim360.com/login

IMPORTANT: Please change your password after first login.
        """
        
        return send_email_smtp(email, subject, html_body, text_body)
        
    except Exception as e:
        logger.error(f"❌ Error sending welcome email: {str(e)}")
        return False
# =====================================================
# 1. REGISTRATION VERIFICATION EMAIL
# =====================================================

def send_verification_email(email: str, first_name: str, verification_token: str) -> bool:
    """
    Send email verification link to newly registered user
    Link expires in 24 hours
    """
    try:
        logger.info(f"📧 Sending verification email to: {email}")
        
        # Build verification link
        base_url = getattr(settings, 'BASE_URL', 'https://calim360.com')
        verification_link = f"{base_url}/verify-email?token={verification_token}"
        
        logger.info(f"🔗 Verification link: {verification_link}")
        
        # HTML Email Body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #1a5f7a 0%, #2762cb 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 600;
                }}
                .icon {{
                    font-size: 48px;
                    margin-bottom: 15px;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .content h2 {{
                    color: #1a5f7a;
                    font-size: 22px;
                    margin-top: 0;
                }}
                .content p {{
                    font-size: 16px;
                    line-height: 1.8;
                    margin: 15px 0;
                }}
                .button-container {{
                    text-align: center;
                    margin: 35px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 16px 40px;
                    background: linear-gradient(135deg, #1a5f7a 0%, #2762cb 100%);
                    color: white !important;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 12px rgba(26, 95, 122, 0.3);
                }}
                .link-box {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 6px;
                    word-break: break-all;
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                    color: #666;
                    margin: 20px 0;
                }}
                .info-box {{
                    background: #e8f4f8;
                    border-left: 4px solid #1a5f7a;
                    padding: 15px 20px;
                    margin: 25px 0;
                    border-radius: 6px;
                }}
                .info-box strong {{
                    color: #1a5f7a;
                    display: block;
                    margin-bottom: 8px;
                }}
                .warning-box {{
                    background: #fff3cd;
                    border-left: 4px solid #f0ad4e;
                    padding: 15px 20px;
                    margin: 25px 0;
                    border-radius: 6px;
                }}
                .warning-box strong {{
                    color: #856404;
                    display: block;
                    margin-bottom: 8px;
                }}
                .footer {{
                    background: #f8f9fa;
                    padding: 30px;
                    text-align: center;
                    color: #666;
                    font-size: 14px;
                    border-top: 1px solid #e9ecef;
                }}
                .footer a {{
                    color: #1a5f7a;
                    text-decoration: none;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon"></div>
                    <h1>Welcome to CALIM 360!</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {first_name},</h2>
                    
                    <p>Thank you for registering with <strong>CALIM 360</strong> - Smart Contract Lifecycle Management System.</p>
                    
                    <p>To complete your registration and activate your account, please verify your email address by clicking the button below:</p>
                    
                    <div class="button-container">
                        <a href="{verification_link}" class="button">Verify Your Email Address</a>
                    </div>
                    
                    <p style="font-size: 14px; color: #666;">If the button doesn't work, copy and paste this link into your browser:</p>
                    <div class="link-box">{verification_link}</div>
                    
                    <div class="info-box">
                        <strong> Important Information:</strong>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">This verification link will expire in <strong>24 hours</strong>. Please verify your email as soon as possible to activate your account.</p>
                    </div>
                    
                    <div class="warning-box">
                        <strong> Security Notice:</strong>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">If you didn't create an account with CALIM 360, please ignore this email. Your email address will not be used without verification.</p>
                    </div>
                    
                    <p style="margin-top: 30px;">Once verified, you'll have access to:</p>
                    <ul style="line-height: 2; color: #555;">
                        <li>Contract Lifecycle Management</li>
                        <li>AI-Powered Contract Analysis</li>
                        <li>Blockchain-Secured Audit Trails</li>
                        <li>Multi-Party Collaboration Tools</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p><strong>CALIM 360</strong> - Smart Contract Lifecycle Management</p>
                    <p>Need help? Contact us at <a href="mailto:{settings.EMAILS_FROM_EMAIL}">{settings.EMAILS_FROM_EMAIL}</a></p>
                    <p style="font-size: 12px; color: #999; margin-top: 15px;">
                        © {datetime.now().year} CALIM 360. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
Welcome to CALIM 360!

Hello {first_name},

Thank you for registering with CALIM 360 - Smart Contract Lifecycle Management System.

To complete your registration and activate your account, please verify your email address by clicking this link:
{verification_link}

This verification link will expire in 24 hours.

If you didn't create an account with CALIM 360, please ignore this email.

---
CALIM 360 - Smart Contract Lifecycle Management
Need help? Contact us at {settings.EMAILS_FROM_EMAIL}
© {datetime.now().year} CALIM 360. All rights reserved.
        """
        
        # Send email
        success = send_email_smtp(
            to_email=email,
            subject=" Verify Your Email - CALIM 360",
            html_body=html_body,
            text_body=text_body
        )
        
        if success:
            logger.info(f" Verification email sent successfully to: {email}")
        else:
            logger.error(f"❌ Failed to send verification email to: {email}")
            logger.info(f"🔗 Verification link (for testing): {verification_link}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error in send_verification_email: {str(e)}", exc_info=True)
        return False

# =====================================================
# 2. PASSWORD RESET EMAIL
# =====================================================

def send_password_reset_email(email: str, first_name: str, reset_link: str) -> bool:
    """
    Send password reset link
    Link expires in 24 hours
    """
    try:
        logger.info(f"📧 Sending password reset email to: {email}")
        logger.info(f"🔗 Reset link: {reset_link}")
        
        # HTML Email Body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #1a5f7a 0%, #2762cb 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 600; }}
                .icon {{ font-size: 48px; margin-bottom: 15px; }}
                .content {{ padding: 40px 30px; }}
                .content h2 {{ color: #1a5f7a; font-size: 22px; margin-top: 0; }}
                .content p {{ font-size: 16px; line-height: 1.8; margin: 15px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{
                    display: inline-block;
                    padding: 16px 40px;
                    background: linear-gradient(135deg, #1a5f7a 0%, #2762cb 100%);
                    color: white !important;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 12px rgba(26, 95, 122, 0.3);
                }}
                .link-box {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 6px;
                    word-break: break-all;
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                    color: #666;
                    margin: 20px 0;
                }}
                .warning-box {{
                    background: #fff3cd;
                    border-left: 4px solid #f0ad4e;
                    padding: 15px 20px;
                    margin: 25px 0;
                    border-radius: 6px;
                }}
                .warning-box strong {{ color: #856404; display: block; margin-bottom: 8px; }}
                .footer {{
                    background: #f8f9fa;
                    padding: 30px;
                    text-align: center;
                    color: #666;
                    font-size: 14px;
                    border-top: 1px solid #e9ecef;
                }}
                .footer a {{ color: #1a5f7a; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon">🔐</div>
                    <h1>Password Reset Request</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {first_name},</h2>
                    
                    <p>We received a request to reset your password for your CALIM 360 account.</p>
                    
                    <p>Click the button below to create a new password. This link will expire in <strong>24 hours</strong> for security reasons.</p>
                    
                    <div class="button-container">
                        <a href="{reset_link}" class="button">Reset Your Password</a>
                    </div>
                    
                    <p style="font-size: 14px; color: #666;">If the button doesn't work, copy and paste this link into your browser:</p>
                    <div class="link-box">{reset_link}</div>
                    
                    <div class="warning-box">
                        <strong>⚠️ Security Notice:</strong>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">If you didn't request this password reset, please ignore this email or contact our support team immediately. Your password will remain unchanged.</p>
                    </div>
                    
                    <p style="margin-top: 30px; font-size: 14px; color: #666;">
                        <strong>What happens next?</strong><br>
                        1. Click the "Reset Your Password" button above<br>
                        2. You'll be taken to a secure page to create a new password<br>
                        3. Enter your new password and confirm it<br>
                        4. Log in with your new password
                    </p>
                </div>
                
                <div class="footer">
                    <p><strong>CALIM 360</strong> - Smart Contract Lifecycle Management</p>
                    <p>Need help? Contact us at <a href="mailto:{settings.EMAILS_FROM_EMAIL}">{settings.EMAILS_FROM_EMAIL}</a></p>
                    <p style="font-size: 12px; color: #999; margin-top: 15px;">
                        © {datetime.now().year} CALIM 360. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
Password Reset Request - CALIM 360

Hello {first_name},

We received a request to reset your password for your CALIM 360 account.

Click this link to reset your password (expires in 24 hours):
{reset_link}

If you didn't request this password reset, please ignore this email.

---
CALIM 360 - Smart Contract Lifecycle Management
Need help? Contact us at {settings.EMAILS_FROM_EMAIL}
© {datetime.now().year} CALIM 360. All rights reserved.
        """
        
        # Send email
        success = send_email_smtp(
            to_email=email,
            subject="🔐 Password Reset Request - CALIM 360",
            html_body=html_body,
            text_body=text_body
        )
        
        if success:
            logger.info(f" Password reset email sent successfully to: {email}")
        else:
            logger.error(f"❌ Failed to send password reset email to: {email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error in send_password_reset_email: {str(e)}", exc_info=True)
        return False

# =====================================================
# 3. PASSWORD CHANGED CONFIRMATION EMAIL
# =====================================================

def send_password_changed_confirmation(email: str, first_name: str) -> bool:
    """
    Send confirmation email after successful password change
    """
    try:
        logger.info(f"📧 Sending password changed confirmation to: {email}")
        
        # HTML Email Body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 600; }}
                .icon {{ font-size: 48px; margin-bottom: 15px; }}
                .content {{ padding: 40px 30px; }}
                .content h2 {{ color: #28a745; font-size: 22px; margin-top: 0; }}
                .content p {{ font-size: 16px; line-height: 1.8; margin: 15px 0; }}
                .info-table {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .info-table table {{ width: 100%; border-collapse: collapse; }}
                .info-table td {{ padding: 8px 0; font-size: 14px; }}
                .info-table td:first-child {{ font-weight: 600; color: #555; width: 40%; }}
                .warning-box {{
                    background: #fff3cd;
                    border-left: 4px solid #f0ad4e;
                    padding: 15px 20px;
                    margin: 25px 0;
                    border-radius: 6px;
                }}
                .warning-box strong {{ color: #856404; display: block; margin-bottom: 8px; }}
                .footer {{
                    background: #f8f9fa;
                    padding: 30px;
                    text-align: center;
                    color: #666;
                    font-size: 14px;
                    border-top: 1px solid #e9ecef;
                }}
                .footer a {{ color: #28a745; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon"></div>
                    <h1>Password Changed Successfully</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {first_name},</h2>
                    
                    <p>Your CALIM 360 account password has been successfully changed.</p>
                    
                    <div class="info-table">
                        <table>
                            <tr>
                                <td>Date & Time:</td>
                                <td>{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</td>
                            </tr>
                            <tr>
                                <td>Account Email:</td>
                                <td>{email}</td>
                            </tr>
                            <tr>
                                <td>Action:</td>
                                <td>Password Reset</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div class="warning-box">
                        <strong> Security Notice:</strong>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">If you did NOT make this change, please contact our support team immediately at <a href="mailto:{settings.EMAILS_FROM_EMAIL}" style="color: #856404; font-weight: 600;">{settings.EMAILS_FROM_EMAIL}</a></p>
                    </div>
                    
                    <p style="margin-top: 25px;">For your security, all active sessions have been logged out. Please log in again with your new password.</p>
                    
                    <p style="font-size: 14px; color: #666; margin-top: 30px;">
                        <strong>Security Tips:</strong><br>
                        • Use a unique password for CALIM 360<br>
                        • Enable two-factor authentication for extra security<br>
                        • Never share your password with anyone<br>
                        • Change your password regularly
                    </p>
                </div>
                
                <div class="footer">
                    <p><strong>CALIM 360</strong> - Smart Contract Lifecycle Management</p>
                    <p>Need help? Contact us at <a href="mailto:{settings.EMAILS_FROM_EMAIL}">{settings.EMAILS_FROM_EMAIL}</a></p>
                    <p style="font-size: 12px; color: #999; margin-top: 15px;">
                        © {datetime.now().year} CALIM 360. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
Password Changed Successfully - CALIM 360

Hello {first_name},

Your CALIM 360 account password has been successfully changed.

Change Details:
- Date & Time: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
- Account Email: {email}
- Action: Password Reset

SECURITY NOTICE:
If you did NOT make this change, please contact our support team immediately at {settings.EMAILS_FROM_EMAIL}

For your security, all active sessions have been logged out. Please log in again with your new password.

---
CALIM 360 - Smart Contract Lifecycle Management
Need help? Contact us at {settings.EMAILS_FROM_EMAIL}
© {datetime.now().year} CALIM 360. All rights reserved.
        """
        
        # Send email
        success = send_email_smtp(
            to_email=email,
            subject=" Password Changed Successfully - CALIM 360",
            html_body=html_body,
            text_body=text_body
        )
        
        if success:
            logger.info(f" Password changed confirmation sent successfully to: {email}")
        else:
            logger.error(f"❌ Failed to send password changed confirmation to: {email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error in send_password_changed_confirmation: {str(e)}", exc_info=True)
        return False

# =====================================================
# 4. WELCOME EMAIL (AFTER EMAIL VERIFICATION)
# =====================================================

def send_welcome_email(email: str, first_name: str) -> bool:
    """
    Send welcome email after successful email verification
    """
    try:
        logger.info(f"📧 Sending welcome email to: {email}")
        
        # HTML Email Body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .content {{ padding: 40px 30px; }}
                .footer {{
                    background: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    color: #666;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">🎉 Welcome to CALIM 360!</h1>
                </div>
                <div class="content">
                    <h2 style="color: #28a745;">Hello {first_name},</h2>
                    <p>Your email has been verified successfully! You can now access all features of CALIM 360.</p>
                    <p>Get started with:</p>
                    <ul>
                        <li>Creating and managing contracts</li>
                        <li>AI-powered contract analysis</li>
                        <li>Secure blockchain audit trails</li>
                        <li>Collaborative workflows</li>
                    </ul>
                </div>
                <div class="footer">
                    <p><strong>CALIM 360</strong></p>
                    <p>© {datetime.now().year} CALIM 360. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        success = send_email_smtp(
            to_email=email,
            subject="🎉 Welcome to CALIM 360!",
            html_body=html_body
        )
        
        if success:
            logger.info(f" Welcome email sent successfully to: {email}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error in send_welcome_email: {str(e)}", exc_info=True)
        return False