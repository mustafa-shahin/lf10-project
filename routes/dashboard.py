from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from routes.utils import get_db, require_login
from models import Application, Person
from services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    if user.person_type == "admin":
        applications = []
        users = db.query(Person).all()
    elif user.person_type == "employee":
        applications = db.query(Application).all()
        users = [] 
    else:
        applications = db.query(Application).filter(Application.person_id == user.id).all()
        users = []

    # Map status to CSS classes for visual styling
    status_class_mapping = {
        "angenommen": "accepted",
        "in bearbeitung": "pending",
        "abgelehnt": "rejected"
    }

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
            decision_display = "Annehmen"
        elif app.decision == "rejected":
            decision_display = "Ablehnen"
        elif app.decision == "pending":
            decision_display = "Ausstehend"
        
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
            "files": app.files 
        })
    
    # Process users for admin view
    user_class_mapping = {
        "admin": "admin",
        "employee": "employee",
        "customer": "customer"
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
        
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "applications": processed_apps,
            "users": processed_users
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

    # Update application status based on decision
    status = ""
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
    

    logger.info(f"Application {app_obj.id} decision by {user.id}: {status}")
    
    db.commit()
    db.refresh(app_obj)
    
    person = db.query(Person).filter(Person.id == app_obj.person_id).first()
    if person:
        try:
            formatted_date = app_obj.created_at.strftime("%d.%m.%Y")
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
    if person_type not in ["admin", "employee", "customer"]:
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