import logging
from sqlalchemy.orm import Session
from models import Notification, Person, Application

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def create_notification(db: Session, recipient_id: int, message: str, 
                           sender_id: int = None, application_id: int = None):
        notification = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            application_id=application_id,
            message=message
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        logger.info(f"Created notification for user {recipient_id}")
        
        return notification
    
    @staticmethod
    def get_unread_notifications(db: Session, user_id: int):
        return db.query(Notification).filter(
            Notification.recipient_id == user_id,
            Notification.is_read == False
        ).all()
    
    @staticmethod
    def mark_notification_read(db: Session, notification_id: int, user_id: int):
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.recipient_id == user_id
        ).first()
        
        if notification:
            notification.is_read = True
            db.commit()
            return True
        return False
    
    @staticmethod
    def request_manager_approval(db: Session, application_id: int, employee_id: int):
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            logger.warning(f"Application {application_id} not found")
            return False
        
        # Find all managers
        managers = db.query(Person).filter(Person.person_type == "manager").all()
        if not managers:
            logger.warning("No managers found to notify")
            return False
        
        # Get employee name
        employee = db.query(Person).filter(Person.id == employee_id).first()
        employee_name = f"{employee.first_name} {employee.second_name}" if employee else "Ein Mitarbeiter"
        
        # Create notification for each manager
        for manager in managers:
            NotificationService.create_notification(
                db=db,
                recipient_id=manager.id,
                message=f"{employee_name} benötigt Ihre Genehmigung für Kreditantrag #{application_id}",
                sender_id=employee_id,
                application_id=application_id
            )
        
        logger.info(f"Approval request sent to managers for application {application_id}")
        return True