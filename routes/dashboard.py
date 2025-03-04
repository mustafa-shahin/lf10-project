from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from routes.utils import get_db, require_login, send_email
from models import Application, Person

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
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
        return RedirectResponse(url="/dashboard", status_code=303)

    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        return RedirectResponse(url="/dashboard", status_code=303)

    if decision == "accept":
        app_obj.status = "angenommen"
    elif decision == "reject":
        app_obj.status = "abgelehnt"

    app_obj.decided_at = datetime.utcnow()
    app_obj.handled_by_id = user.id
    db.commit()
    db.refresh(app_obj)
    status ="angenommen" if decision == "accept" else "abgelehnt"
    formatted_date = app_obj.created_at.strftime("%d.%m.%Y")
    # Send email
    person = app_obj.person
    if person:
        subject = "Loan Status Update"
       
        body = (
            f"Hallo {person.first_name},\n\n"
            f"Ihr Darlehensantrag von {formatted_date} wurde {status}.\n\n"
        )
        send_email(to_address=person.email, subject=subject, body=body)

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
        # if not admin => maybe show an error or just redirect
        return RedirectResponse(url="/dashboard", status_code=303)

    # Fetch user and update their role
    user_obj = db.query(Person).filter(Person.id == user_id).first()
    if user_obj:
        user_obj.person_type = person_type
        db.commit()
        db.refresh(user_obj)

    # After updating, go back to dashboard
    return RedirectResponse(url="/dashboard", status_code=303)

