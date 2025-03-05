import uuid
import smtplib
from email.mime.text import MIMEText
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from db import SessionLocal
from models import Person
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_TLS

# Simple in-memory session store:
sessions = {}  # { session_id: person_id }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[Person]:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None
    person_id = sessions[session_id]
    person = db.query(Person).filter(Person.id == person_id).first()
    return person

def require_login(request: Request, db: Session = Depends(get_db)) -> Person:
    user = get_current_user(request, db=db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    else:
        return user

def create_session_cookie(response, person_id: int):
    session_id = str(uuid.uuid4())
    sessions[session_id] = person_id
    response.set_cookie(key="session_id", value=session_id, httponly=True)

def clear_session_cookie(response, request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    response.delete_cookie("session_id")

def send_email(to_address: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_address

    if not SMTP_HOST:
        print("SMTP not configured. Email not sent.")
        return

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    try:
        if SMTP_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to_address], msg.as_string())
        print("Email sent to", to_address)
    finally:
        server.quit()
