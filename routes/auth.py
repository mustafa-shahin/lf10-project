import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uuid
from models import Person
from routes.utils import get_db, send_email, create_session_cookie, clear_session_cookie, sessions

templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.get("/register", response_class=HTMLResponse)
def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register", response_class=HTMLResponse)
def post_register(
    request: Request,
    salutation: str = Form(...),
    title: str = Form(""),
    first_name: str = Form(...),
    second_name: str = Form(...),
    street: str = Form(...),
    house_number: str = Form(...),
    zip_code: str = Form(...),
    city: str = Form(...),
    country: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if email already exists
    existing = db.query(Person).filter_by(email=email).first()
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already in use."}
        )

    # Count how many users we already have
    count_users = db.query(Person).count()
    if count_users == 0:
        # first user => admin
        person_type = "admin"
    else:
        # subsequent users => customer (or your logic)
        person_type = "customer"

    # Hash password
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    # Create Person
    new_person = Person(
        salutation=salutation,
        title=title,
        first_name=first_name,
        second_name=second_name,
        street=street,
        house_number=house_number,
        zip_code=zip_code,
        city=city,
        country=country,
        person_type=person_type,
        email=email,
        password_hash=hashed_pw.decode("utf-8")
    )
    db.add(new_person)
    db.commit()
    db.refresh(new_person)

    # create session
    session_id = str(uuid.uuid4())
    sessions[session_id] = new_person.id

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_id", value=session_id, httponly=True)
    return response

@router.get("/login", response_class=HTMLResponse)
def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None})

@router.post("/login", response_class=HTMLResponse)
def post_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    person = db.query(Person).filter_by(email=email).first()
    if not person:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Passwort oder E-Mail-Adresse falsch."}
        )

    # Check password
    if bcrypt.hashpw(password.encode("utf-8"), person.password_hash.encode("utf-8")) != person.password_hash.encode("utf-8"):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Passwort oder E-Mail-Adresse falsch."}
        )

    # Create session
    response = RedirectResponse(url="/dashboard", status_code=303)
    create_session_cookie(response, person.id)
    return response

@router.get("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response, request)
    return response

@router.get("/forgot_password", response_class=HTMLResponse)
def get_forgot_password(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot_password", response_class=HTMLResponse)
def post_forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    person = db.query(Person).filter_by(email=email).first()
    if not person:
        return templates.TemplateResponse(
            "forgot_password.html", 
            {"request": request, "message": "Eine Email wurde gesendet."}
        )

    token = secrets.token_urlsafe(32)
    person.reset_token = token
    person.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    reset_link = f"http://127.0.0.1:8000/reset_password?token={token}"
    body = f"Link zum Zurücksetzen des Passworts: {reset_link}"
    send_email(person.email, "Password Reset", body)

    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "message": "Eine Email wurde gesendet."}
    )

@router.get("/reset_password", response_class=HTMLResponse)
def get_reset_password(request: Request, token: str):
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

@router.post("/reset_password", response_class=HTMLResponse)
def post_reset_password(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    person = db.query(Person).filter_by(reset_token=token).first()
    if not person or not person.reset_token_expiration:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "error": "Invalid token.", "token": token}
        )

    if datetime.utcnow() > person.reset_token_expiration:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "error": "Token expired.", "token": token}
        )

    hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    person.password_hash = hashed_pw.decode("utf-8")
    person.reset_token = None
    person.reset_token_expiration = None
    db.commit()

    return RedirectResponse(url="/login", status_code=303)
