import logging
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any, List, Optional

from models import Application, Person, Notification, File
from routes.utils import get_db, require_login
from services.email_service import email_service
from services.calculations import LoanDecision

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def process_application_for_display(app: Application, db: Session) -> Dict[str, Any]:
    # Map status to CSS classes for visual styling
    status_class_mapping = {
        "angenommen": "accepted",
        "in bearbeitung": "pending",
        "abgelehnt": "rejected",
        "Warten auf Auszahlung": "accepted",
        "Angebot abgelehnt": "rejected"
    }
    
    # Safe conversion helper function
    def safe_float_round(value, digits=2):
        if value is None:
            return None
        try:
            return round(float(value), digits)
        except (ValueError, TypeError):
            return value
    
    app_css_class = status_class_mapping.get(app.status, "unknown")
    
    # Format decision for display
    decision_display = ""
    if app.decision == "approved":
        decision_display = "Annehmen"
    elif app.decision == "rejected":
        decision_display = "Ablehnen"
    elif app.decision == "pending":
        decision_display = "Ausstehend"
    
    # Get customer info
    customer = db.query(Person).filter(Person.id == app.person_id).first()
    customer_name = f"{customer.first_name} {customer.second_name}" if customer else "Unbekannt"
    
    # Get handler info if available
    handler_name = "Nicht zugewiesen"
    if app.handled_by_id:
        handler = db.query(Person).filter(Person.id == app.handled_by_id).first()
        if handler:
            handler_name = f"{handler.first_name} {handler.second_name}"
    
    # Get files
    files = db.query(File).filter(File.application_id == app.id).all()
    
    # Determine if application needs manager approval based on thresholds
    needs_manager_approval = getattr(app, 'needs_manager_approval', False)
    
    # For employee view, check thresholds to show the appropriate buttons
    requires_manager_check = False
    if app.status == "in bearbeitung" and not needs_manager_approval:
        if hasattr(app, 'bonitaet') and app.bonitaet is not None:
            try:
                boni_score = float(app.bonitaet)
                if boni_score < 670:
                    requires_manager_check = True
            except (ValueError, TypeError):
                pass
        
        if hasattr(app, 'dscr') and app.dscr is not None and not requires_manager_check:
            try:
                dscr = float(app.dscr)
                if dscr < 1.4:
                    requires_manager_check = True
            except (ValueError, TypeError):
                pass
    
    # Check if the application is approved and an offer can be created
    is_approved = app.status == "angenommen"
    can_create_offer = is_approved and not getattr(app, 'has_offer', False)
    
    # Determine who made the decision
    decision_maker_name = None
    if app.decided_at and app.handled_by_id:
        if app.manager_approved is not None:  # Manager made the decision
            managers = db.query(Person).filter(Person.person_type == "manager").all()
            for manager in managers:
                decision_maker_name = f"{manager.first_name} {manager.second_name} (Manager)"
                break
        else:  # Employee made the decision
            employee = db.query(Person).filter(Person.id == app.handled_by_id).first()
            if employee:
                decision_maker_name = f"{employee.first_name} {employee.second_name} (Mitarbeiter)"
    
    return {
        "id": app.id,
        "loan_type": app.loan_type,
        "loan_subtype": app.loan_subtype,
        "requested_amount": app.requested_amount,
        "term_in_years": app.term_in_years,
        "status": app.status,
        "status_class": app_css_class, 
        "created_at": app.created_at.strftime("%Y-%m-%d") if app.created_at else "",
        "decided_at": app.decided_at.strftime("%Y-%m-%d") if app.decided_at else "",
        "decision": decision_display,
        "reason": app.reason,
        "dscr": safe_float_round(app.dscr),
        "ccr": safe_float_round(app.ccr),
        "bonitaet": safe_float_round(app.bonitaet),
        "files": files,
        "customer_name": customer_name,
        "handler_name": handler_name,
        "decision_maker_name": decision_maker_name,
        "needs_manager_approval": needs_manager_approval,
        "requires_manager_check": requires_manager_check,
        "manager_approved": getattr(app, 'manager_approved', None),
        "approval_note": getattr(app, 'approval_note', None),
        "repayment_amount": app.repayment_amount,
        "is_approved": is_approved,
        "can_create_offer": can_create_offer
    }

def get_unread_notifications(db: Session, user_id: int) -> List[Notification]:
    return db.query(Notification).filter(
        Notification.recipient_id == user_id,
        Notification.is_read == False
    ).order_by(Notification.created_at.desc()).all()

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    try:
        # Get appropriate applications based on user type
        if user.person_type == "admin":
            # Admin sees all applications for reference but focuses on user management
            applications = []
            users = db.query(Person).all()
        elif user.person_type in ["employee", "manager", "director"]:
            # Staff see all applications
            applications = db.query(Application).order_by(Application.created_at.desc()).all()
            users = []
        else:  # customer
            # Customers only see their own applications
            applications = db.query(Application).filter(
                Application.person_id == user.id
            ).order_by(Application.created_at.desc()).all()
            users = []
        
        # Process applications for display
        processed_apps = []
        if user.person_type != "admin":
            processed_apps = [process_application_for_display(app, db) for app in applications]
        
        # Process users for admin view
        processed_users = []
        if user.person_type == "admin":
            user_class_mapping = {
                "admin": "admin",
                "employee": "employee",
                "customer": "customer",
                "manager": "manager",
                "director": "director"
            }
            
            for u in users:
                processed_users.append({
                    "id": u.id,
                    "name": f"{u.first_name} {u.second_name}",
                    "email": u.email,
                    "person_type": u.person_type,
                    "person_class": user_class_mapping.get(u.person_type, "unknown")
                })
        
        # Get unread notifications
        notifications = get_unread_notifications(db, user.id)
        
        # Render the appropriate dashboard template
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "applications": processed_apps,
                "users": processed_users,
                "notifications": notifications,
                "unread_count": len(notifications)
            }
        )
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html", 
            {"request": request, "error_code": 500, "message": "Fehler beim Laden des Dashboards", "user": user}
        )

@router.post("/dashboard/decision")
def process_loan_decision(
    request: Request,
    application_id: int = Form(...),
    decision: str = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only employees can make loan decisions
    if user.person_type != "employee":
        logger.warning(f"Unauthorized user ({user.person_type}) attempted to make loan decision")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Find the application
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

    # Check if application requires manager approval based on thresholds
    needs_approval = False
    
    # Check boni score
    if hasattr(app_obj, 'bonitaet') and app_obj.bonitaet is not None:
        try:
            boni_score = float(app_obj.bonitaet)
            if boni_score < 670:
                needs_approval = True
        except (ValueError, TypeError):
            pass
    
    # Check DSCR
    if hasattr(app_obj, 'dscr') and app_obj.dscr is not None:
        try:
            dscr = float(app_obj.dscr)
            if dscr < 1.4:
                needs_approval = True
        except (ValueError, TypeError):
            pass
    
    # If needs approval, redirect to manager approval process instead
    if needs_approval:
        logger.warning(f"Employee {user.id} attempted to directly approve/reject application {application_id} that needs manager approval")
        raise HTTPException(
            status_code=400, 
            detail="Dieser Antrag benötigt die Genehmigung eines Managers. Bitte nutzen Sie die Manager-Genehmigungsfunktion."
        )
    
    # Process decision for applications that don't need manager approval
    if decision == "accept":
        status = "angenommen"
        app_obj.status = status
        app_obj.decision = "approved"
    elif decision == "reject":
        status = "abgelehnt"
        app_obj.status = status
        app_obj.decision = "rejected"
    else:
        logger.warning(f"Invalid decision: {decision}")
        raise HTTPException(status_code=400, detail="Ungültige Entscheidung")

    # Update application metadata
    app_obj.decided_at = datetime.now()
    app_obj.handled_by_id = user.id
    
    logger.info(f"Application {app_obj.id} decision by {user.id}: {app_obj.status}")
    
    db.commit()
    db.refresh(app_obj)
    
    # Send email notification
    person = db.query(Person).filter(Person.id == app_obj.person_id).first()
    if person:
        try:
            formatted_date = app_obj.created_at.strftime("%d.%m.%Y")
            email_service.send_loan_status_email(
                to_address=person.email,
                first_name=person.first_name,
                application_date=formatted_date,
                loan_type=app_obj.loan_type,
                status=app_obj.status,
                reason=app_obj.reason
            )
            logger.info(f"Sent loan status email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")

    return RedirectResponse(url="/dashboard", status_code=303)
@router.post("/dashboard/update-user")
def update_user_role(
    request: Request,
    user_id: int = Form(...),
    person_type: str = Form(...),
    db: Session = Depends(get_db),
    admin: Person = Depends(require_login)
):
    # Only admin can update user roles
    if admin.person_type != "admin":
        logger.warning(f"Non-admin user ({admin.person_type}) attempted to update user role")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Validate role
    valid_roles = ["admin", "employee", "customer", "manager", "director"]
    if person_type not in valid_roles:
        logger.warning(f"Invalid role in update request: {person_type}")
        raise HTTPException(status_code=400, detail="Ungültiger Benutzertyp")
    
    # Find and update the user
    user_obj = db.query(Person).filter(Person.id == user_id).first()
    if not user_obj:
        logger.warning(f"User {user_id} not found for role update")
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        
    # Update user role
    user_obj.person_type = person_type
    db.commit()
    db.refresh(user_obj)
    
    logger.info(f"User {user_id} role updated to {person_type} by admin {admin.id}")

    # After updating, go back to dashboard
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/request-approval")
def request_manager_approval_endpoint(
    request: Request,
    application_id: int = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only employees can request manager approval
    if user.person_type != "employee":
        logger.warning(f"Non-employee user ({user.person_type}) attempted to request manager approval")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Find the application
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

    # Set application as needing manager approval
    app_obj.needs_manager_approval = True
    app_obj.handled_by_id = user.id
    app_obj.decision = "pending"  # Mark as pending until manager decides
    db.commit()
    
    # Request manager approval
    request_manager_approval(db, application_id, user.id)
    
    return RedirectResponse(url="/dashboard", status_code=303)

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
    
    # Get customer name
    customer = db.query(Person).filter(Person.id == application.person_id).first()
    customer_name = f"{customer.first_name} {customer.second_name}" if customer else "Unbekannt"
    
    # Create notification for each manager
    for manager in managers:
        notification = Notification(
            recipient_id=manager.id,
            sender_id=employee_id,
            application_id=application_id,
            message=f"{employee_name} benötigt Ihre Genehmigung für Kreditantrag #{application_id} ({application.loan_type}) von {customer_name} - {application.requested_amount}€"
        )
        db.add(notification)
    
    db.commit()
    logger.info(f"Approval request sent to managers for application {application_id}")
    return True

@router.post("/dashboard/manager-decision")
def process_manager_decision(
    request: Request,
    application_id: int = Form(...),
    decision: str = Form(...),  # "approve" or "reject"
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only managers can make approval decisions
    if user.person_type != "manager":
        logger.warning(f"Non-manager user ({user.person_type}) attempted to make approval decision")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")
    
    # Find the application
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")
    
    # Check if application needs approval
    if not app.needs_manager_approval:
        logger.warning(f"Application {application_id} doesn't need manager approval")
        raise HTTPException(status_code=400, detail="Dieser Antrag benötigt keine Genehmigung")
    
    # Update application based on decision
    app.manager_approved = (decision == "approve")
    app.approval_note = notes
    
    if app.manager_approved:
        app.status = "angenommen"
        app.decision = "approved"
        app.decided_at = datetime.now()
    else:  
        app.status = "abgelehnt"
        app.decision = "rejected"
        app.decided_at = datetime.now()
    
    db.commit()
    db.refresh(app)
    
    # Notify the handling employee
    if app.handled_by_id:
        approved_text = "genehmigt" if app.manager_approved else "abgelehnt"
        note_text = f" Notiz: {notes}" if notes else ""
        
        notification = Notification(
            recipient_id=app.handled_by_id,
            sender_id=user.id,
            application_id=app.id,
            message=f"Manager hat Antrag #{app.id} {approved_text}.{note_text}"
        )
        db.add(notification)
        db.commit()
    
    # Send email to customer
    person = db.query(Person).filter(Person.id == app.person_id).first()
    if person and (app.status == "angenommen" or app.status == "abgelehnt"):
        try:
            formatted_date = app.created_at.strftime("%d.%m.%Y")
            email_service.send_loan_status_email(
                to_address=person.email,
                first_name=person.first_name,
                application_date=formatted_date,
                loan_type=app.loan_type,
                status=app.status,
                reason=app.approval_note if not app.manager_approved else app.reason
            )
            logger.info(f"Sent loan status email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/manager-decision")
def process_manager_decision(
    request: Request,
    application_id: int = Form(...),
    decision: str = Form(...),  # "approve" or "reject"
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only managers can make approval decisions
    if user.person_type != "manager":
        logger.warning(f"Non-manager user ({user.person_type}) attempted to make approval decision")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")
    
    # Find the application
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")
    
    # Check if application needs approval
    if not app.needs_manager_approval:
        logger.warning(f"Application {application_id} doesn't need manager approval")
        raise HTTPException(status_code=400, detail="Dieser Antrag benötigt keine Genehmigung")
    
    # Update application based on decision
    app.manager_approved = (decision == "approve")
    app.approval_note = notes
    
    # If manager approved and employee approved, set status to approved
    if app.manager_approved and app.decision == "approved":
        app.status = "angenommen"
        app.decided_at = datetime.now()
    elif not app.manager_approved:
        # If manager rejected, reject the application
        app.status = "abgelehnt"
        app.decided_at = datetime.now()
    
    db.commit()
    db.refresh(app)
    
    # Notify the handling employee
    if app.handled_by_id:
        approved_text = "genehmigt" if app.manager_approved else "abgelehnt"
        note_text = f" Notiz: {notes}" if notes else ""
        
        notification = Notification(
            recipient_id=app.handled_by_id,
            sender_id=user.id,
            application_id=app.id,
            message=f"Manager hat Antrag #{app.id} {approved_text}.{note_text}"
        )
        db.add(notification)
        db.commit()
    
    # Send email to customer if application status changed
    person = db.query(Person).filter(Person.id == app.person_id).first()
    if person and (app.status == "angenommen" or app.status == "abgelehnt"):
        try:
            formatted_date = app.created_at.strftime("%d.%m.%Y")
            email_service.send_loan_status_email(
                to_address=person.email,
                first_name=person.first_name,
                application_date=formatted_date,
                loan_type=app.loan_type,
                status=app.status,
                reason=app.approval_note if not app.manager_approved else app.reason
            )
            logger.info(f"Sent loan status email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/mark-notification-read")
def mark_notification_read(
    request: Request,
    notification_id: int = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Find the notification
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == user.id
    ).first()
    
    if not notification:
        logger.warning(f"Notification {notification_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Benachrichtigung nicht gefunden")
    
    # Mark as read
    notification.is_read = True
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/manager-decision")
def process_manager_decision(
    request: Request,
    application_id: int = Form(...),
    decision: str = Form(...),  # "approve" or "reject"
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only managers can make approval decisions
    if user.person_type != "manager":
        logger.warning(f"Non-manager user ({user.person_type}) attempted to make approval decision")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")
    
    # Find the application
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")
    
    # Check if application needs approval
    if not app.needs_manager_approval:
        logger.warning(f"Application {application_id} doesn't need manager approval")
        raise HTTPException(status_code=400, detail="Dieser Antrag benötigt keine Genehmigung")
    
    # Update application based on decision
    app.manager_approved = (decision == "approve")
    app.approval_note = notes
    
    # If manager approves the loan, set to approved
    if app.manager_approved:
        app.status = "angenommen"
        app.decision = "approved"
    else:  # If manager rejects, set to rejected
        app.status = "abgelehnt"
        app.decision = "rejected"
    
    # Save decision metadata
    app.decided_at = datetime.now()
    
    db.commit()
    db.refresh(app)
    
    # Notify the handling employee
    if app.handled_by_id:
        approved_text = "genehmigt" if app.manager_approved else "abgelehnt"
        note_text = f" Notiz: {notes}" if notes else ""
        
        notification = Notification(
            recipient_id=app.handled_by_id,
            sender_id=user.id,
            application_id=app.id,
            message=f"Manager hat Antrag #{app.id} {approved_text}.{note_text}"
        )
        db.add(notification)
        db.commit()
    
    # Send email to customer
    person = db.query(Person).filter(Person.id == app.person_id).first()
    if person and (app.status == "angenommen" or app.status == "abgelehnt"):
        try:
            formatted_date = app.created_at.strftime("%d.%m.%Y")
            email_service.send_loan_status_email(
                to_address=person.email,
                first_name=person.first_name,
                application_date=formatted_date,
                loan_type=app.loan_type,
                status=app.status,
                reason=app.approval_note if not app.manager_approved else app.reason
            )
            logger.info(f"Sent loan status email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/create-offer")
def create_offer(
    request: Request,
    application_id: int = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only employees can create offers
    if user.person_type != "employee":
        logger.warning(f"Non-employee user ({user.person_type}) attempted to create an offer")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Find the application
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")
    
    # Check if application is approved
    if app.status != "angenommen":
        logger.warning(f"Cannot create offer for non-approved application {application_id}")
        raise HTTPException(status_code=400, detail="Angebote können nur für genehmigte Anträge erstellt werden")
    
    # Check if an offer already exists
    if getattr(app, 'has_offer', False):
        logger.warning(f"Offer already exists for application {application_id}")
        raise HTTPException(status_code=400, detail="Für diesen Antrag existiert bereits ein Angebot")
    
    # Create a simple offer (this is a placeholder, you'd add your actual offer creation logic)
    try:
        # Update application to mark that an offer exists
        app.has_offer = True
        db.commit()
        
        # Notify the customer about the offer
        notification = Notification(
            recipient_id=app.person_id,
            sender_id=user.id,
            application_id=app.id,
            message=f"Ein Angebot für Ihren Kreditantrag #{app.id} wurde erstellt. Bitte überprüfen Sie Ihr Angebot."
        )
        db.add(notification)
        db.commit()
        
        
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Error creating offer: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Fehler beim Erstellen des Angebots")