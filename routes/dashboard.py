# routes/dashboard.py
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from typing import List, Optional

from routes.utils import get_db, require_login, get_current_user
from models import Application, Person, Notification
from services.email_service import email_service
from services.notification_service import notification_service
from services.loan_calculation import loan_calculation_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_dashboard_template(user_type: str) -> str:
    if user_type == "customer":
        return "dashboard.html"  
    elif user_type == "manager":
        return "dashboard_manager.html"
    elif user_type == "employee" or user_type == "director":
        return "dashboard_employee.html"
    elif user_type == "admin":
        return "dashboard_employee.html"  
    else:
        return "dashboard.html"  # Fallback to generic dashboard

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Choose dashboard template based on user type
    dashboard_template = get_dashboard_template(user.person_type)
    
    # Get applications based on user type
    if user.person_type == "customer":
        applications = db.query(Application).filter(Application.person_id == user.id).all()
        users = []
        managers = []
    elif user.person_type == "manager":
        # Managers see all applications and those needing their approval
        applications = db.query(Application).all()
        # Get applications needing manager approval
        approval_needed = db.query(Application).filter(
            Application.needs_manager_approval == True,
            Application.manager_approved.is_(None)
        ).all()
        users = []
        managers = []
    elif user.person_type == "admin":
        applications = []
        users = db.query(Person).all()
        managers = db.query(Person).filter(Person.person_type == "manager").all()
    else:  # employee, director
        applications = db.query(Application).all()
        users = []
        managers = db.query(Person).filter(Person.person_type == "manager").all()

    # Map status to CSS classes for visual styling
    status_class_mapping = {
        "angenommen": "accepted",
        "in bearbeitung": "pending",
        "abgelehnt": "rejected"
    }

    # Get notifications for the user
    notifications = notification_service.get_notifications_for_user(db, user.id)
    unread_notifications = [n for n in notifications if not n.read]

    # Safe conversion helper function
    def safe_float_round(value, digits=2):
        if value is None:
            return None
        try:
            return round(float(value), digits)
        except (ValueError, TypeError):
            return value

    # Process applications for display
    processed_apps = []
    for app in applications:
        app_css_class = status_class_mapping.get(app.status, "unknown")
        
        # Format decision for display
        decision_display = ""
        if app.decision == "approved":
            decision_display = "Angenommen"
        elif app.decision == "rejected":
            decision_display = "Abgelehnt"
        elif app.decision == "pending":
            decision_display = "Ausstehend"
        
        # Get customer name for application
        customer = db.query(Person).filter(Person.id == app.person_id).first()
        customer_name = f"{customer.first_name} {customer.second_name}" if customer else "Unbekannt"
        
        processed_apps.append({
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
            "files": app.files,
            "needs_manager_approval": app.needs_manager_approval,
            "manager_approved": app.manager_approved,
            "customer_name": customer_name,
            "interest_rate": app.interest_rate,
            "monthly_payment": app.monthly_payment,
            "offer_created": app.offer_created,
            "offer_sent": app.offer_sent
        })
    
    # Process users for admin view
    user_class_mapping = {
        "admin": "admin",
        "employee": "employee",
        "customer": "customer",
        "manager": "manager",
        "director": "director"
    }

    processed_users = []
    for u in users:
        processed_users.append({
            "id": u.id,
            "name": f"{u.first_name} {u.second_name}",
            "email": u.email,
            "person_type": u.person_type,
            "person_class": user_class_mapping.get(u.person_type, "unknown")
        })

    # Process managers for employee view
    processed_managers = []
    for m in managers:
        processed_managers.append({
            "id": m.id,
            "name": f"{m.first_name} {m.second_name}",
            "email": m.email
        })
        
    return templates.TemplateResponse(
        dashboard_template,
        {
            "request": request,
            "user": user,
            "applications": processed_apps,
            "users": processed_users,
            "managers": processed_managers,
            "notifications": notifications,
            "unread_count": len(unread_notifications)
        }
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

    # Check if this application already needs manager approval or has reason requiring it
    if app_obj.reason == "Zusätzliche Sicherheit erforderlich (1 Monat Verzögerung)" and not app_obj.needs_manager_approval:
        logger.warning(f"Application {application_id} requires manager approval but attempt was made to make direct decision")
        raise HTTPException(
            status_code=400, 
            detail="Dieser Antrag benötigt Manager-Genehmigung. Bitte benachrichtigen Sie den Manager."
        )
    
    # Check if application needs manager approval based on DSCR/CCR values
    needs_approval = False
    if app_obj.loan_type == "Baudarlehen" and not app_obj.needs_manager_approval:
        if ((1 <= app_obj.dscr < 2 and app_obj.ccr < 1) or 
            (app_obj.dscr >= 2 and app_obj.ccr < 0.75)):
            needs_approval = True
            app_obj.reason = "Zusätzliche Sicherheit erforderlich (1 Monat Verzögerung)"
    
    # If needs approval and decision is accept, mark for manager approval
    if needs_approval and decision == "accept":
        app_obj.needs_manager_approval = True
        app_obj.status = "in bearbeitung"  # Keep status as processing
        app_obj.decision = "pending"
        
        # Send notification to managers
        notification_service.notify_managers_for_approval(db, app_obj.id, user.id)
        
        # Get managers and send emails
        managers = db.query(Person).filter(Person.person_type == "manager").all()
        employee_name = f"{user.first_name} {user.second_name}"
        
        for manager in managers:
            email_service.send_manager_approval_needed_email(
                to_address=manager.email,
                first_name=manager.first_name,
                application_id=app_obj.id,
                employee_name=employee_name,
                loan_type=app_obj.loan_type,
                amount=app_obj.requested_amount
            )
            
        db.commit()
        logger.info(f"Application {app_obj.id} sent for manager approval by {user.id}")
        
        return RedirectResponse(url="/dashboard", status_code=303)
    
    # Update application status based on decision
    status = ""
    if decision == "accept":
        status = "angenommen"
        app_obj.status = status
        app_obj.decision = "approved"
        
        # Calculate monthly payment using the loan calculation service
        monthly_payment = loan_calculation_service.calculate_monthly_payment(
            principal=app_obj.requested_amount,
            annual_interest_rate=app_obj.interest_rate,
            term_years=app_obj.term_in_years
        )
        app_obj.monthly_payment = monthly_payment
        app_obj.offer_created = True
        
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

    logger.info(f"Application {app_obj.id} decision by {user.id}: {status}")
    
    db.commit()
    db.refresh(app_obj)
    
    # Send email to customer
    person = db.query(Person).filter(Person.id == app_obj.person_id).first()
    if person:
        try:
            formatted_date = app_obj.created_at.strftime("%d.%m.%Y")
            
            # If approved, send loan offer email
            if status == "angenommen":
                email_service.send_loan_offer_email(
                    to_address=person.email,
                    first_name=person.first_name,
                    application_id=app_obj.id,
                    loan_type=app_obj.loan_type,
                    amount=app_obj.requested_amount,
                    interest_rate=app_obj.interest_rate,
                    monthly_payment=app_obj.monthly_payment,
                    term=app_obj.term_in_years
                )
                app_obj.offer_sent = True
                db.commit()
                logger.info(f"Sent loan offer email to {person.email}")
            else:
                # If rejected, send standard status email
                email_service.send_loan_status_email(
                    to_address=person.email,
                    first_name=person.first_name,
                    application_date=formatted_date,
                    loan_type=app_obj.loan_type,
                    status=status,
                    reason=app_obj.reason
                )
                logger.info(f"Sent loan status email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")

    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/process-loan")
def process_loan_application(
    request: Request,
    application_id: int = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    """Mark a loan application as being processed"""
    # Only employees can process loans
    if user.person_type not in ["employee", "manager"]:
        logger.warning(f"Unauthorized user ({user.person_type}) attempted to process a loan")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Find the application
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

    # Always update to "in bearbeitung" status when this endpoint is called
    app_obj.status = "in bearbeitung"
    app_obj.decision = "pending"
    app_obj.handled_by_id = user.id
    
    db.commit()
    db.refresh(app_obj)
    
    # Send processing email
    person = db.query(Person).filter(Person.id == app_obj.person_id).first()
    if person:
        try:
            email_service.send_loan_processing_email(
                to_address=person.email,
                first_name=person.first_name,
                application_id=app_obj.id,
                loan_type=app_obj.loan_type
            )
            logger.info(f"Sent loan processing email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send processing email: {str(e)}")
    
    logger.info(f"Application {app_obj.id} marked as processing by {user.id}")
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/manager-decision")
def manager_approval_decision(
    request: Request,
    application_id: int = Form(...),
    decision: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    """Manager approval decision for loan applications"""
    # Only managers can make manager approval decisions
    if user.person_type != "manager":
        logger.warning(f"Unauthorized user ({user.person_type}) attempted to make manager decision")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Find the application
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

    # Check if this application needs manager approval
    if not app_obj.needs_manager_approval:
        logger.warning(f"Application {application_id} does not need manager approval")
        raise HTTPException(status_code=400, detail="Dieser Antrag benötigt keine Manager-Genehmigung")
    
    # Update manager approval status
    approved = decision == "approve"
    app_obj.manager_approved = approved
    app_obj.manager_id = user.id
    app_obj.manager_notes = notes
    
    # If manager approved, keep status as processing
    # If manager rejected, update status to rejected
    if not approved:
        app_obj.status = "abgelehnt"
        app_obj.decision = "rejected"
        app_obj.decided_at = datetime.now()
        
        # Send email to customer about rejection
        person = db.query(Person).filter(Person.id == app_obj.person_id).first()
        if person:
            try:
                formatted_date = app_obj.created_at.strftime("%d.%m.%Y")
                email_service.send_loan_status_email(
                    to_address=person.email,
                    first_name=person.first_name,
                    application_date=formatted_date,
                    loan_type=app_obj.loan_type,
                    status="abgelehnt",
                    reason=f"Manager Entscheidung: {notes}" if notes else "Nicht genehmigt durch Manager"
                )
                logger.info(f"Sent loan rejection email to {person.email}")
            except Exception as e:
                logger.error(f"Failed to send rejection email: {str(e)}")
    
    # Notify the original handler (employee) of the manager's decision
    if app_obj.handled_by_id:
        notification_service.notify_employee_of_manager_decision(
            db=db,
            application_id=app_obj.id,
            manager_id=user.id,
            employee_id=app_obj.handled_by_id,
            approved=approved
        )
    
    db.commit()
    logger.info(f"Manager {user.id} {decision}d application {app_obj.id}")
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/mark-notification-read")
def mark_notification_read(
    request: Request,
    notification_id: int = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    """Mark a notification as read"""
    success = notification_service.mark_notification_as_read(db, notification_id, user.id)
    if not success:
        logger.warning(f"Failed to mark notification {notification_id} as read for user {user.id}")
    
    # Redirect back to dashboard
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/create-loan-offer")
def create_loan_offer(
    request: Request,
    application_id: int = Form(...),
    interest_rate: float = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    """Create a loan offer with calculated payments"""
    # Only employees can create loan offers
    if user.person_type not in ["employee", "manager"]:
        logger.warning(f"Unauthorized user ({user.person_type}) attempted to create a loan offer")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Find the application
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")
    
    # Check that application is approved or has manager approval
    if app_obj.decision != "approved" and not (app_obj.needs_manager_approval and app_obj.manager_approved):
        logger.warning(f"Cannot create offer for non-approved application {application_id}")
        raise HTTPException(status_code=400, detail="Angebot kann nur für genehmigte Anträge erstellt werden")
    
    # Update application with interest rate
    app_obj.interest_rate = interest_rate
    
    # Calculate monthly payment
    monthly_payment = loan_calculation_service.calculate_monthly_payment(
        principal=app_obj.requested_amount,
        annual_interest_rate=interest_rate,
        term_years=app_obj.term_in_years
    )
    
    app_obj.monthly_payment = monthly_payment
    app_obj.offer_created = True
    app_obj.status = "angenommen"
    app_obj.decision = "approved"
    app_obj.decided_at = datetime.now()
    
    db.commit()
    db.refresh(app_obj)
    
    # Send loan offer email
    person = db.query(Person).filter(Person.id == app_obj.person_id).first()
    if person:
        try:
            email_service.send_loan_offer_email(
                to_address=person.email,
                first_name=person.first_name,
                application_id=app_obj.id,
                loan_type=app_obj.loan_type,
                amount=app_obj.requested_amount,
                interest_rate=app_obj.interest_rate,
                monthly_payment=app_obj.monthly_payment,
                term=app_obj.term_in_years
            )
            app_obj.offer_sent = True
            db.commit()
            logger.info(f"Sent loan offer email to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send loan offer email: {str(e)}")
    
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/update-user")
def update_user_role(
    request: Request,
    user_id: int = Form(...),
    person_type: str = Form(...),
    db: Session = Depends(get_db),
    admin: Person = Depends(require_login)
):
    # Only admin can update users
    if admin.person_type != "admin":
        logger.warning(f"Non-admin user ({admin.person_type}) attempted to update user role")
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Validate person_type
    if person_type not in ["admin", "employee", "customer", "manager", "director"]:
        logger.warning(f"Invalid person type: {person_type}")
        raise HTTPException(status_code=400, detail="Ungültiger Benutzertyp")

    # Fetch user and update their role
    user_obj = db.query(Person).filter(Person.id == user_id).first()
    if not user_obj:
        logger.warning(f"User {user_id} not found")
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        
    # Update user role
    user_obj.person_type = person_type
    db.commit()
    db.refresh(user_obj)
    
    logger.info(f"User {user_id} role updated to {person_type} by admin {admin.id}")

    # After updating, go back to dashboard
    return RedirectResponse(url="/dashboard", status_code=303)