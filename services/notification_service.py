# services/notification_service.py
import logging
from sqlalchemy.orm import Session
from models import Notification, Person, Application
from typing import List, Optional

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        recipient_id: int,
        message: str,
        sender_id: Optional[int] = None,
        application_id: Optional[int] = None,
        notification_type: str = "info"
    ) -> Notification:
        #Create a new notification for a user
        try:
            notification = Notification(
                recipient_id=recipient_id,
                sender_id=sender_id,
                application_id=application_id,
                message=message,
                notification_type=notification_type
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            logger.info(f"Created notification {notification.id} for user {recipient_id}")
            return notification
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    def get_notifications_for_user(db: Session, user_id: int, unread_only: bool = False) -> List[Notification]:
        ##Get notifications for a specific user
        query = db.query(Notification).filter(Notification.recipient_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.read == False)
            
        return query.order_by(Notification.created_at.desc()).all()

    @staticmethod
    def mark_notification_as_read(db: Session, notification_id: int, user_id: int) -> bool:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.recipient_id == user_id
        ).first()
        
        if not notification:
            return False
            
        notification.read = True
        db.commit()
        return True

    @staticmethod
    def notify_managers_for_approval(db: Session, application_id: int, employee_id: int) -> List[int]:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            logger.error(f"Application {application_id} not found")
            return []
            
        managers = db.query(Person).filter(Person.person_type == "manager").all()
        
        if not managers:
            logger.warning("No managers found in the system")
            return []
            
        # Get employee name
        employee = db.query(Person).filter(Person.id == employee_id).first()
        employee_name = f"{employee.first_name} {employee.second_name}" if employee else "Ein Mitarbeiter"
        
        # Create notifications for each manager
        notification_ids = []
        for manager in managers:
            message = f"{employee_name} benötigt Ihre Genehmigung für den Kreditantrag #{application.id} (Betrag: {application.requested_amount}€)"
            notification = NotificationService.create_notification(
                db=db,
                recipient_id=manager.id,
                sender_id=employee_id,
                application_id=application_id,
                message=message,
                notification_type="approval_request"
            )
            notification_ids.append(notification.id)
            
        return notification_ids

    @staticmethod
    def notify_employee_of_manager_decision(
        db: Session, 
        application_id: int, 
        manager_id: int, 
        employee_id: int,
        approved: bool
    ) -> Optional[int]:
        # Get the application
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            logger.error(f"Application {application_id} not found")
            return None
            
        # Get manager name
        manager = db.query(Person).filter(Person.id == manager_id).first()
        manager_name = f"{manager.first_name} {manager.second_name}" if manager else "Ein Manager"
        
        # Create notification for the employee
        status = "genehmigt" if approved else "abgelehnt"
        message = f"{manager_name} hat den Kreditantrag #{application.id} {status}"
        
        notification = NotificationService.create_notification(
            db=db,
            recipient_id=employee_id,
            sender_id=manager_id,
            application_id=application_id,
            message=message,
            notification_type="info"
        )
        
        return notification.id

notification_service = NotificationService()