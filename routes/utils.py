import uuid
import logging
from fastapi import Request, HTTPException, Depends, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from db import SessionLocal
from models import Person

# Configure logging
logger = logging.getLogger(__name__)

# Simple in-memory session store
# Using new format: session_id -> {user_id: id, expires: datetime}
sessions: Dict[str, Dict[str, Any]] = {}

# Session configuration
SESSION_EXPIRY_DAYS = 7

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def clean_expired_sessions():
    now = datetime.now()
    expired_sessions = []
    
    for session_id, data in sessions.items():
        # Handle both the old format (int) and new format (dict)
        if isinstance(data, dict) and "expires" in data:
            if data["expires"] < now:
                expired_sessions.append(session_id)
        elif isinstance(data, int):
            # Convert old format to new format
            sessions[session_id] = {
                "user_id": data,
                "expires": now + timedelta(days=SESSION_EXPIRY_DAYS)
            }
            logger.debug(f"Converted old format session to new format: {session_id}")
    
    for session_id in expired_sessions:
        del sessions[session_id]
        
    if expired_sessions:
        logger.info(f"Cleaned {len(expired_sessions)} expired sessions")

def get_current_user(
    request: Request, 
    db: Session = Depends(get_db),
    session_id: Optional[str] = Cookie(None)
) -> Optional[Person]:
    # Clean expired sessions occasionally
    clean_expired_sessions()
    
    # Debug session state
    logger.debug(f"get_current_user called, session count: {len(sessions)}")
    logger.debug(f"Session cookie: {session_id}")
    
    if not session_id:
        logger.debug("No session cookie found")
        return None
    
    if session_id not in sessions:
        logger.debug(f"Session ID not found in sessions dictionary: {session_id}")
        return None
    
    # Get session data
    session_data = sessions[session_id]
    logger.debug(f"Session data: {session_data}")
    
    # Handle different session formats
    person_id = None
    if isinstance(session_data, int):
        # Old format - direct user ID
        person_id = session_data
        # Convert to new format
        sessions[session_id] = {
            "user_id": person_id,
            "expires": datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)
        }
        logger.debug(f"Converted old session format for {session_id}")
    elif isinstance(session_data, dict):
        person_id = session_data.get("user_id")
        expires = session_data.get("expires")
        
        # Check if session is expired
        if not person_id:
            logger.debug(f"No user_id in session data")
            del sessions[session_id]
            return None
            
        if not expires:
            logger.debug(f"No expiration in session data")
            del sessions[session_id]
            return None
            
        if expires < datetime.now():
            logger.debug(f"Session expired: {expires}")
            del sessions[session_id]
            return None
    else:
        logger.warning(f"Invalid session data type: {type(session_data)}")
        del sessions[session_id]
        return None
    
    user = db.query(Person).filter(Person.id == person_id).first()
    
    if user:
        logger.debug(f"Found user: id={user.id}, type={user.person_type}")
    else:
        logger.warning(f"User with ID {person_id} not found in database")
        del sessions[session_id]
        
    return user

def require_login(
    request: Request, 
    db: Session = Depends(get_db),
    session_id: Optional[str] = Cookie(None)
) -> Person:

    logger.debug("require_login called")
    user = get_current_user(request, db, session_id)
    if not user:
        logger.debug("User not logged in, redirecting to login page")
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user

def create_session_cookie(response, person_id: int):
    session_id = str(uuid.uuid4())
    expires = datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)
    
    sessions[session_id] = {
        "user_id": person_id,
        "expires": expires
    }
    
    http_expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Set cookie with same expiry as session
    response.set_cookie(
        key="session_id", 
        value=session_id, 
        httponly=True,
        expires=http_expires,
        path="/",  # Make sure cookie is available for all paths
        samesite="lax"  # Protects against CSRF
    )
    
    logger.info(f"Created session for user {person_id}, session_id: {session_id}")
    logger.debug(f"Current sessions after creation: {sessions}")

def clear_session_cookie(response, request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
        logger.info(f"Cleared session {session_id}")
    
    # Ensure cookie is properly deleted with the same path
    response.delete_cookie(key="session_id", path="/")