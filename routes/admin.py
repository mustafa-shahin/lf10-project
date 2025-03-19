from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from routes.utils import get_db, require_login
from models import Person

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin/users", response_class=HTMLResponse)
def admin_user_list(
    request: Request,
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    # Only an admin can manage other users
    if user.person_type != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    all_users = db.query(Person).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "all_users": all_users
        }
    )

@router.post("/admin/users/update_role", response_class=HTMLResponse)
def update_role(
    request: Request,
    person_id: int = Form(...),
    new_role: str = Form(...),
    db: Session = Depends(get_db),
    user: Person = Depends(require_login)
):
    if user.person_type != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    # Check that new_role is valid
    if new_role not in ("admin", "employee", "customer", "manager", "director"):
        return RedirectResponse(url="/admin/users", status_code=303)

    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return RedirectResponse(url="/admin/users", status_code=303)

    # Update role
    person.person_type = new_role
    db.commit()
    db.refresh(person)

    return RedirectResponse(url="/admin/users", status_code=303)
