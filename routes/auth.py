import bcrypt
import secrets
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uuid
from models import Person
from routes.utils import get_db, create_session_cookie, clear_session_cookie, sessions
from services.email_service import email_service
logger = logging.getLogger(__name__)



templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.get("/register", response_class=HTMLResponse)
def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": None})

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
    logger.info(f"Registration attempt for email: {email}")
    
    # Check if email already exists
    existing = db.query(Person).filter_by(email=email).first()
    if existing:
        logger.warning(f"Registration failed: Email {email} already exists")
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email bereits in Verwendung.", "user": None}
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
    try:
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    except Exception as e:
        logger.error(f"Password hashing error: {str(e)}")
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.", "user": None}
        )

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
    
    try:
        db.add(new_person)
        db.commit()
        db.refresh(new_person)
        logger.info(f"User registered successfully: {new_person.id} (type: {person_type})")
    except Exception as e:
        logger.error(f"Database error during registration: {str(e)}")
        db.rollback()
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Datenbankfehler. Bitte versuchen Sie es später erneut.", "user": None}
        )

    # Send welcome email
    try:
        email_service.send_welcome_email(
            to_address=email,
            first_name=first_name
        )
        logger.info(f"Welcome email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")

    # Create response and session
    response = RedirectResponse(url="/", status_code=303)
    create_session_cookie(response, new_person.id)
    
    cookie_value = response.headers.get("set-cookie", "")
    logger.debug(f"Registration cookie header: {cookie_value}")
    
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
    logger.info(f"Login attempt for email: {email}")
    
    # Clear existing sessions for debugging
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        logger.debug(f"Removing existing session on login: {session_id}")
        del sessions[session_id]
    
    # Find the user
    person = db.query(Person).filter_by(email=email).first()
    if not person:
        logger.warning(f"Login failed: User with email {email} not found")
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Passwort oder E-Mail-Adresse falsch.", "user": None}
        )

    # Check password
    try:
        pw_matched = bcrypt.checkpw(password.encode("utf-8"), person.password_hash.encode("utf-8"))
        if not pw_matched:
            logger.warning(f"Login failed: Incorrect password for user {email}")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Passwort oder E-Mail-Adresse falsch.", "user": None}
            )
    except Exception as e:
        logger.error(f"Password check error for {email}: {str(e)}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.", "user": None}
        )

    # Login successful
    logger.info(f"Login successful for user {person.id} ({email}), type: {person.person_type}")
    
    # Create a response that redirects to root
    response = RedirectResponse(url="/", status_code=303)
    
    # Create a session directly here for debugging
    session_id = str(uuid.uuid4())
    expires = datetime.now() + timedelta(days=7)
    
    # Store session
    sessions[session_id] = {
        "user_id": person.id,
        "expires": expires
    }
    
    # Format for HTTP
    http_expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Set cookie directly
    response.set_cookie(
        key="session_id", 
        value=session_id, 
        httponly=True,
        expires=http_expires,
        path="/",
        samesite="lax"
    )
    
    # Debug the cookie
    logger.debug(f"Login created session {session_id} for user {person.id}")
    logger.debug(f"Sessions after login: {sessions}")
    cookie_value = response.headers.get("set-cookie", "")
    logger.debug(f"Login cookie header: {cookie_value}")
    
    return response

@router.get("/logout")
def logout(request: Request):
    logger.info("Logout requested")
    response = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(response, request)
    return response

@router.get("/forgot_password", response_class=HTMLResponse)
def get_forgot_password(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "user": None})

@router.post("/forgot_password", response_class=HTMLResponse)
def post_forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Password reset requested for: {email}")
    person = db.query(Person).filter_by(email=email).first()
    if not person:
        # Don't reveal if email exists for security
        logger.info(f"Password reset requested for non-existent email: {email}")
        return templates.TemplateResponse(
            "forgot_password.html", 
            {"request": request, "message": "Falls die E-Mail-Adresse in unserem System registriert ist, wurde eine E-Mail zum Zurücksetzen des Passworts gesendet.", "user": None}
        )

    # Generate secure token
    token = secrets.token_urlsafe(32)
    person.reset_token = token
    person.reset_token_expiration = datetime.now() + timedelta(hours=1)
    db.commit()
    logger.info(f"Password reset token generated for user {person.id}")

    # Create reset URL
    host = request.headers.get("host", "localhost:8000")
    scheme = request.headers.get("x-forwarded-proto", "http")
    reset_link = f"{scheme}://{host}/reset_password?token={token}"
    
    # Send password reset email
    try:
        email_service.send_password_reset_email(
            to_address=person.email,
            first_name=person.first_name,
            reset_link=reset_link
        )
        logger.info(f"Password reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")

    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "message": "Falls die E-Mail-Adresse in unserem System registriert ist, wurde eine E-Mail zum Zurücksetzen des Passworts gesendet.", "user": None}
    )

@router.get("/reset_password", response_class=HTMLResponse)
def get_reset_password(request: Request, token: str):
    logger.info(f"Password reset page accessed with token: {token[:8]}...")
    
    # Validate token
    db = next(get_db())
    person = db.query(Person).filter_by(reset_token=token).first()
    
    if not person or not person.reset_token_expiration:
        logger.warning(f"Invalid reset token: {token[:8]}...")
        return templates.TemplateResponse(
            "reset_error.html", 
            {"request": request, "error": "Ungültiger oder abgelaufener Token", "user": None}
        )
    
    now = datetime.now()
    expiration = person.reset_token_expiration
    
    # Convert both to naive UTC datetimes if needed
    if hasattr(now, 'tzinfo') and now.tzinfo:
        now = now.replace(tzinfo=None)
    if hasattr(expiration, 'tzinfo') and expiration.tzinfo:
        expiration = expiration.replace(tzinfo=None)
        
    if now > expiration:
        logger.warning(f"Expired reset token: {token[:8]}...")
        return templates.TemplateResponse(
            "reset_error.html", 
            {"request": request, "error": "Token abgelaufen", "user": None}
        )
    
    logger.info(f"Valid reset token for user {person.id}")    
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token, "user": None})

@router.post("/reset_password", response_class=HTMLResponse)
def post_reset_password(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Password reset attempt with token: {token[:8]}...")
    
    person = db.query(Person).filter_by(reset_token=token).first()
    if not person or not person.reset_token_expiration:
        logger.warning(f"Invalid reset token on submit: {token[:8]}...")
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "error": "Ungültiger Token", "token": token, "user": None}
        )

    now = datetime.now()
    expiration = person.reset_token_expiration
    
    # Convert both to naive UTC datetimes if needed
    if hasattr(now, 'tzinfo') and now.tzinfo:
        now = now.replace(tzinfo=None)
    if hasattr(expiration, 'tzinfo') and expiration.tzinfo:
        expiration = expiration.replace(tzinfo=None)
        
    if now > expiration:
        logger.warning(f"Expired reset token on submit: {token[:8]}...")
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "error": "Token abgelaufen", "token": token, "user": None}
        )

    # Update password
    try:
        hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        person.password_hash = hashed_pw.decode("utf-8")
        person.reset_token = None
        person.reset_token_expiration = None
        db.commit()
        logger.info(f"Password reset successful for user {person.id}")
        
        # Send confirmation email
        try:
            email_service.send_password_changed_email(
                to_address=person.email,
                first_name=person.first_name
            )
            logger.info(f"Password changed email sent to {person.email}")
        except Exception as e:
            logger.error(f"Failed to send password changed email: {str(e)}")
        
        # Auto-login
        response = RedirectResponse(url="/dashboard", status_code=303)
        
        # Create session directly
        session_id = str(uuid.uuid4())
        expires = datetime.now() + timedelta(days=7)
        
        # Store session
        sessions[session_id] = {
            "user_id": person.id,
            "expires": expires
        }
        
        # Format for HTTP
        http_expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        # Set cookie directly
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            httponly=True,
            expires=http_expires,
            path="/",
            samesite="lax"
        )
        
        logger.debug(f"Password reset: created session {session_id} for user {person.id}")
        return response
        
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "error": "Fehler beim Zurücksetzen des Passworts", "token": token, "user": None}
        )