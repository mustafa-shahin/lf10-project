from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging

from routes.utils import get_db, require_login
from models import Notification, Person
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/notifications", response_class=HTMLResponse)
def get_notifications(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    #Get all notifications for the current user
    notifications = notification_service.get_notifications_for_user(db, user.id)
    
    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "user": user,
            "notifications": notifications,
            "unread_count": len([n for n in notifications if not n.read])
        }
    )

@router.post("/notifications/mark-read")
def mark_notification_read(
    request: Request,
    notification_id: int = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    success = notification_service.mark_notification_as_read(db, notification_id, user.id)
    
    if not success:
        logger.warning(f"Failed to mark notification {notification_id} as read for user {user.id}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Failed to mark notification as read"}
        )
    
    return JSONResponse(
        content={"success": True, "message": "Notification marked as read"}
    )

@router.post("/notifications/mark-all-read")
def mark_all_notifications_read(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Get all unread notifications
    notifications = notification_service.get_notifications_for_user(db, user.id, unread_only=True)
    
    success_count = 0
    for notification in notifications:
        success = notification_service.mark_notification_as_read(db, notification.id, user.id)
        if success:
            success_count += 1
    
    logger.info(f"Marked {success_count} of {len(notifications)} notifications as read for user {user.id}")
    
    # Redirect back to notifications page
    return RedirectResponse(url="/notifications", status_code=303)

@router.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == user.id
    ).first()
    
    if not notification:
        logger.warning(f"Notification {notification_id} not found or not owned by user {user.id}")
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Notification not found"}
        )
    
    try:
        db.delete(notification)
        db.commit()
        logger.info(f"Deleted notification {notification_id} for user {user.id}")
        return JSONResponse(
            content={"success": True, "message": "Notification deleted"}
        )
    except Exception as e:
        logger.error(f"Error deleting notification {notification_id}: {str(e)}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Error deleting notification"}
        )