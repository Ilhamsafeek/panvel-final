"""
Background Scheduler for Notifications and Obligation Monitoring
app/tasks/scheduler.py

Runs periodic tasks:
- Daily obligation scans
- Reminder notifications
- Cleanup old notifications
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

from app.core.database import get_db_session
from app.services.obligation_monitor_service import ObligationMonitorService
from app.services.notification_service import NotificationService
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class NotificationScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.setup_jobs()
    
    def setup_jobs(self):
        """Setup all scheduled jobs"""
        
        # Daily obligation scan at 8:00 AM AST (Qatar time)
        self.scheduler.add_job(
            self.scan_obligations_job,
            CronTrigger(hour=8, minute=0, timezone='Asia/Qatar'),
            id='daily_obligation_scan',
            name='Daily Obligation Scan',
            replace_existing=True
        )
        
        # Hourly check for urgent obligations
        self.scheduler.add_job(
            self.urgent_obligation_check,
            IntervalTrigger(hours=1),
            id='hourly_urgent_check',
            name='Hourly Urgent Obligation Check',
            replace_existing=True
        )
        
        # Send reminder notifications every 6 hours
        self.scheduler.add_job(
            self.send_pending_reminders,
            IntervalTrigger(hours=6),
            id='reminder_notifications',
            name='Send Reminder Notifications',
            replace_existing=True
        )
        
        # Cleanup old notifications weekly (Sunday at 2 AM)
        self.scheduler.add_job(
            self.cleanup_old_notifications,
            CronTrigger(day_of_week='sun', hour=2, minute=0, timezone='Asia/Qatar'),
            id='weekly_cleanup',
            name='Weekly Notification Cleanup',
            replace_existing=True
        )
        
        # Retry failed notifications every 30 minutes
        self.scheduler.add_job(
            self.retry_failed_notifications,
            IntervalTrigger(minutes=30),
            id='retry_failed',
            name='Retry Failed Notifications',
            replace_existing=True
        )
        
        logger.info(" Notification scheduler jobs configured")
    
    async def scan_obligations_job(self):
        """Daily obligation scan job"""
        try:
            logger.info(" Starting daily obligation scan...")
            
            with get_db_session() as db:
                service = ObligationMonitorService(db)
                stats = service.scan_obligations()
                
                logger.info(f" Obligation scan completed: {stats}")
                
        except Exception as e:
            logger.error(f" Error in obligation scan job: {str(e)}")
    
    async def urgent_obligation_check(self):
        """Hourly check for urgent obligations (due within 24 hours)"""
        try:
            logger.info(" Checking urgent obligations...")
            
            with get_db_session() as db:
                from app.models.obligation import Obligation, ObligationStatus
                from datetime import datetime, timedelta
                from sqlalchemy import and_
                
                # Get obligations due within 24 hours
                tomorrow = datetime.utcnow() + timedelta(days=1)
                
                urgent_obligations = db.query(Obligation).filter(
                    and_(
                        Obligation.status.in_([
                            ObligationStatus.PENDING,
                            ObligationStatus.IN_PROGRESS,
                            ObligationStatus.AT_RISK
                        ]),
                        Obligation.due_date <= tomorrow.date(),
                        Obligation.due_date >= datetime.utcnow().date()
                    )
                ).all()
                
                service = ObligationMonitorService(db)
                notification_service = NotificationService(db)
                
                for obligation in urgent_obligations:
                    # Send urgent reminder
                    message = f"""
                    <h3>URGENT: Obligation Due Within 24 Hours</h3>
                    <p><strong>Obligation:</strong> {obligation.obligation_title}</p>
                    <p><strong>Due Date:</strong> {obligation.due_date.strftime('%Y-%m-%d')}</p>
                    <p>This obligation is due within 24 hours. Please take immediate action.</p>
                    """
                    
                    notification_service.create_notification(
                        recipient_id=obligation.owner_id,
                        subject=f"URGENT: {obligation.obligation_title} Due Tomorrow",
                        message=message,
                        notification_type="email",
                        priority="critical"
                    )
                
                logger.info(f" Processed {len(urgent_obligations)} urgent obligations")
                
        except Exception as e:
            logger.error(f" Error in urgent obligation check: {str(e)}")
    
    async def send_pending_reminders(self):
        """Send reminder notifications for pending approvals"""
        try:
            logger.info(" Sending reminder notifications...")
            
            with get_db_session() as db:
                from app.models.workflow import ApprovalRequest
                from datetime import datetime, timedelta
                
                # Get pending approvals older than 6 hours
                six_hours_ago = datetime.utcnow() - timedelta(hours=6)
                
                pending_approvals = db.query(ApprovalRequest).filter(
                    and_(
                        ApprovalRequest.action.is_(None),
                        ApprovalRequest.created_at <= six_hours_ago,
                        ApprovalRequest.reminder_sent_count < 5  # Max 5 reminders
                    )
                ).all()
                
                notification_service = NotificationService(db)
                
                for approval in pending_approvals:
                    message = f"""
                    <h3>Reminder: Approval Pending</h3>
                    <p>You have a pending approval request that requires your attention.</p>
                    <p><strong>Contract:</strong> {approval.contract.contract_number if approval.contract else 'N/A'}</p>
                    <p>Please review and take action on this approval request.</p>
                    """
                    
                    notification_service.create_notification(
                        recipient_id=approval.approver_id,
                        subject="Reminder: Pending Approval Request",
                        message=message,
                        notification_type="email",
                        priority="normal"
                    )
                    
                    approval.reminder_sent_count += 1
                    approval.last_reminder_at = datetime.utcnow()
                
                db.commit()
                logger.info(f" Sent {len(pending_approvals)} reminder notifications")
                
        except Exception as e:
            logger.error(f" Error sending reminders: {str(e)}")
    
    async def cleanup_old_notifications(self):
        """Cleanup old read notifications"""
        try:
            logger.info(" Cleaning up old notifications...")
            
            with get_db_session() as db:
                service = NotificationService(db)
                deleted = service.cleanup_old_notifications(days=90)
                
                logger.info(f" Cleaned up {deleted} old notifications")
                
        except Exception as e:
            logger.error(f" Error cleaning up notifications: {str(e)}")
    
    async def retry_failed_notifications(self):
        """Retry failed notification sends"""
        try:
            logger.info(" Retrying failed notifications...")
            
            with get_db_session() as db:
                from app.models.notification import Notification, NotificationStatus
                
                # Get failed notifications with retry count < 3
                failed_notifications = db.query(Notification).filter(
                    and_(
                        Notification.status == NotificationStatus.FAILED,
                        Notification.retry_count < 3
                    )
                ).limit(50).all()
                
                service = NotificationService(db)
                
                for notification in failed_notifications:
                    try:
                        if notification.notification_type == "email":
                            service._send_email_notification(notification)
                        elif notification.notification_type == "sms":
                            service._send_sms_notification(notification)
                        
                    except Exception as e:
                        logger.error(f"Failed to retry notification {notification.id}: {str(e)}")
                
                logger.info(f" Retried {len(failed_notifications)} failed notifications")
                
        except Exception as e:
            logger.error(f" Error retrying notifications: {str(e)}")
    
    def start(self):
        """Start the scheduler"""
        try:
            self.scheduler.start()
            logger.info(" Notification scheduler started")
        except Exception as e:
            logger.error(f" Failed to start scheduler: {str(e)}")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        try:
            self.scheduler.shutdown()
            logger.info(" Notification scheduler stopped")
        except Exception as e:
            logger.error(f" Error shutting down scheduler: {str(e)}")


# Global scheduler instance
scheduler = NotificationScheduler()


# Add to FastAPI startup/shutdown events
def start_scheduler():
    """Start scheduler on application startup"""
    scheduler.start()


def stop_scheduler():
    """Stop scheduler on application shutdown"""
    scheduler.shutdown()


