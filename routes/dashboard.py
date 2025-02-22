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
def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # If admin => show admin_users.html
    if user.person_type == "admin":
        applications = db.query(Application).all()
        users = db.query(Person).all()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "applications": applications,
                "users": users
            }
        )
    elif user.person_type == "employee":
        # Employees see all applications
        applications = db.query(Application).all()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "applications": applications,
                "users": []  # no user management for employees
            }
        )
    else:
        # customers see only their own apps
        applications = db.query(Application).filter(Application.person_id == user.id).all()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "applications": applications,
                "users": []
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
    # Only employees (and maybe admin, if you like) can accept/reject
    if user.person_type not in ("employee", "admin"):
        return RedirectResponse(url="/dashboard", status_code=303)

    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        return RedirectResponse(url="/dashboard", status_code=303)

    if decision == "approved":
        app_obj.status = "angenommen"
    elif decision == "rejected":
        app_obj.status = "abgelehnt"

    app_obj.decided_at = datetime.utcnow()
    app_obj.handled_by_id = user.id
    db.commit()
    db.refresh(app_obj)
    status ="angenommen" if decision == "approved" else "abgelehnt"
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

