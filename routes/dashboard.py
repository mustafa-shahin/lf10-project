from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from routes.utils import get_db, require_login
from models import Application, Person
from services.email_service  import email_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    if user.person_type == "admin":
        applications = db.query(Application).all()
        users = db.query(Person).all()
    elif user.person_type == "employee":
        applications = db.query(Application).all()
        users = [] 
    else:
        applications = db.query(Application).filter(Application.person_id == user.id).all()
        users = []

    # Map status to CSS classes
    status_class_mapping = {
        "angenommen": "accepted",
        "in bearbeitung": "pending",
        "abgelehnt": "rejected"
    }

    processed_apps = []
    for app in applications:
        app_css_class = status_class_mapping.get(app.status, "unknown")
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
            "decision": app.decision,
            "reason": app.reason,
            "files": app.files 
        })
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
            "person_class": user_class_mapping.get(u.person_type, "unknown")  # Precomputed class
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
    if user.person_type not in ("employee", "admin"):
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

    # Update status based on decision
    status = ""
    if decision == "accept":
        status = "angenommen"
        app_obj.status = status
    elif decision == "reject":
        status = "abgelehnt"
        app_obj.status = status
    else:
        raise HTTPException(status_code=400, detail="Ungültige Entscheidung")

    # Update application metadata
    app_obj.decided_at = datetime.now()
    app_obj.handled_by_id = user.id
    db.commit()
    db.refresh(app_obj)
    
    # Send email notification to customer
    person = db.query(Person).filter(Person.id == app_obj.person_id).first()
    if person:
        formatted_date = app_obj.created_at.strftime("%d.%m.%Y")
        email_service.send_loan_status_email(
            to_address=person.email,
            first_name=person.first_name,
            application_date=formatted_date,
            loan_type=app_obj.loan_type,
            status=status,
            reason=app_obj.reason
        )

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
        raise HTTPException(status_code=403, detail="Unzureichende Berechtigungen")

    # Validate person_type
    if person_type not in ["admin", "employee", "customer"]:
        raise HTTPException(status_code=400, detail="Ungültiger Benutzertyp")

    # Fetch user and update their role
    user_obj = db.query(Person).filter(Person.id == user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        
    user_obj.person_type = person_type
    db.commit()
    db.refresh(user_obj)

    # After updating, go back to dashboard
    return RedirectResponse(url="/dashboard", status_code=303)