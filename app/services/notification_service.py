# =====================================================
# FILE: app/services/notification_service.py
# Notification Delivery Service
# =====================================================

from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import List, Dict, Optional
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service to create and deliver notifications
    """
    
    NOTIFICATION_TYPES = [
        "workflow", "approval", "signature", "obligation",
        "escalation", "system", "reminder"
    ]
    
    PRIORITY_LEVELS = ["low", "normal", "high", "urgent"]
    
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "system",
        priority: str = "normal",
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        send_email: bool = False,
        send_sms: bool = False
    ) -> Dict:
        """Create notification and optionally send email/SMS"""
        try:
            # Insert notification record
            query = text("""
                INSERT INTO notifications 
                (user_id, title, message, type, priority,
                 entity_type, entity_id, is_read, created_at)
                VALUES 
                (:user_id, :title, :message, :type, :priority,
                 :entity_type, :entity_id, 0, NOW())
            """)
            
            db.execute(query, {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type,
                "priority": priority,
                "entity_type": entity_type,
                "entity_id": entity_id
            })
            
            notification_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            db.commit()
            
            # Get user email for delivery
            if send_email or send_sms:
                user = db.execute(
                    text("SELECT email, mobile_number FROM users WHERE id = :id"),
                    {"id": user_id}
                ).first()
                
                if user and send_email and user.email:
                    NotificationService._send_email(
                        user.email, title, message, priority
                    )
                
                if user and send_sms and user.mobile_number:
                    NotificationService._send_sms(
                        user.mobile_number, message
                    )
            
            return {
                "success": True,
                "notification_id": notification_id
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating notification: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def create_bulk_notifications(
        db: Session,
        user_ids: List[int],
        title: str,
        message: str,
        notification_type: str = "system",
        priority: str = "normal",
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None
    ) -> Dict:
        """Create same notification for multiple users"""
        try:
            for user_id in user_ids:
                db.execute(text("""
                    INSERT INTO notifications 
                    (user_id, title, message, type, priority,
                     entity_type, entity_id, is_read, created_at)
                    VALUES 
                    (:user_id, :title, :message, :type, :priority,
                     :entity_type, :entity_id, 0, NOW())
                """), {
                    "user_id": user_id,
                    "title": title,
                    "message": message,
                    "type": notification_type,
                    "priority": priority,
                    "entity_type": entity_type,
                    "entity_id": entity_id
                })
            
            db.commit()
            
            return {
                "success": True,
                "count": len(user_ids)
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating bulk notifications: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """Get notifications for user"""
        sql = """
            SELECT id, title, message, type, priority,
                   entity_type, entity_id, is_read, created_at
            FROM notifications
            WHERE user_id = :user_id
        """
        
        if unread_only:
            sql += " AND is_read = 0"
        
        sql += " ORDER BY created_at DESC LIMIT :limit"
        
        result = db.execute(text(sql), {
            "user_id": user_id,
            "limit": limit
        })
        
        return [dict(row._mapping) for row in result]
    
    @staticmethod
    def mark_as_read(db: Session, notification_id: int, user_id: int) -> bool:
        """Mark notification as read"""
        try:
            db.execute(text("""
                UPDATE notifications 
                SET is_read = 1, read_at = NOW()
                WHERE id = :id AND user_id = :user_id
            """), {
                "id": notification_id,
                "user_id": user_id
            })
            db.commit()
            return True
        except:
            db.rollback()
            return False
    
    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        """Mark all notifications as read"""
        try:
            result = db.execute(text("""
                UPDATE notifications 
                SET is_read = 1, read_at = NOW()
                WHERE user_id = :user_id AND is_read = 0
            """), {"user_id": user_id})
            db.commit()
            return result.rowcount
        except:
            db.rollback()
            return 0
    
    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """Get count of unread notifications"""
        result = db.execute(text("""
            SELECT COUNT(*) FROM notifications
            WHERE user_id = :user_id AND is_read = 0
        """), {"user_id": user_id})
        return result.scalar() or 0
    
    @staticmethod
    def _send_email(
        to_email: str,
        subject: str,
        body: str,
        priority: str = "normal"
    ) -> bool:
        """Send email notification"""
        try:
            # Email configuration from settings
            smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = getattr(settings, 'SMTP_PORT', 587)
            smtp_user = getattr(settings, 'SMTP_USER', '')
            smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
            from_email = getattr(settings, 'FROM_EMAIL', 'noreply@calim360.qa')
            
            if not smtp_user or not smtp_password:
                logger.warning("Email not configured, skipping")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = f"{'🔴 URGENT: ' if priority == 'urgent' else ''}{subject}"
            
            # HTML body
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: #1a5f7a; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
                        <h2 style="margin: 0;">{subject}</h2>
                    </div>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 0 0 8px 8px;">
                        <p>{body}</p>
                        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                        <p style="color: #666; font-size: 12px;">
                            This is an automated notification from CALIM 360.
                            <br>Please do not reply to this email.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    @staticmethod
    def _send_sms(phone_number: str, message: str) -> bool:
        """Send SMS notification (placeholder)"""
        # Implement with Twilio, AWS SNS, or local provider
        logger.info(f"SMS to {phone_number}: {message[:50]}...")
        return True


# Notification templates
class NotificationTemplates:
    """Pre-defined notification templates"""
    
    @staticmethod
    def contract_created(contract_number: str, title: str) -> Dict:
        return {
            "title": "New Contract Created",
            "message": f"Contract {contract_number} - {title} has been created and saved as draft.",
            "type": "system"
        }
    
    @staticmethod
    def approval_required(contract_number: str, title: str, stage: str) -> Dict:
        return {
            "title": f"⏳ Approval Required: {stage}",
            "message": f"Contract {contract_number} - {title} requires your {stage.lower()} approval.",
            "type": "approval",
            "priority": "high"
        }
    
    @staticmethod
    def contract_approved(contract_number: str, title: str, approver: str) -> Dict:
        return {
            "title": " Contract Approved",
            "message": f"Contract {contract_number} - {title} has been approved by {approver}.",
            "type": "workflow"
        }
    
    @staticmethod
    def contract_rejected(contract_number: str, title: str, reason: str) -> Dict:
        return {
            "title": " Contract Rejected",
            "message": f"Contract {contract_number} - {title} was rejected. Reason: {reason}",
            "type": "workflow",
            "priority": "high"
        }
    
    @staticmethod
    def sla_warning(contract_number: str, hours_remaining: int) -> Dict:
        return {
            "title": " SLA Warning",
            "message": f"Contract {contract_number} has {hours_remaining} hours remaining until SLA deadline.",
            "type": "escalation",
            "priority": "high"
        }
    
    @staticmethod
    def sla_breach(contract_number: str, stage: str) -> Dict:
        return {
            "title": "🔴 SLA BREACH - Immediate Action Required",
            "message": f"Contract {contract_number} has breached SLA at {stage} stage. Escalation initiated.",
            "type": "escalation",
            "priority": "urgent"
        }
    
    @staticmethod
    def signature_required(contract_number: str, title: str) -> Dict:
        return {
            "title": "✍️ Signature Required",
            "message": f"Contract {contract_number} - {title} is ready for your signature.",
            "type": "signature",
            "priority": "high"
        }
    
    @staticmethod
    def obligation_due(obligation_title: str, due_date: str) -> Dict:
        return {
            "title": "📅 Obligation Due Soon",
            "message": f"Obligation '{obligation_title}' is due on {due_date}. Please take action.",
            "type": "obligation"
        }
    
    @staticmethod
    def contract_expiring(contract_number: str, days: int) -> Dict:
        return {
            "title": f" Contract Expiring in {days} Days",
            "message": f"Contract {contract_number} will expire in {days} days. Consider renewal.",
            "type": "reminder",
            "priority": "high" if days <= 30 else "normal"
        }