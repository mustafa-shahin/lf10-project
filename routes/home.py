import logging
from fastapi import Request, APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from models import Person
from routes.utils import get_db, get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/home", response_class=HTMLResponse)
def get_home(
    request: Request,
    user: Optional[Person] = Depends(get_current_user),
    db: Session = Depends(get_db) 
):
    logger.debug(f"Home page accessed, user: {user.id if user else None}")
    
    # If user is logged in and not a customer, redirect to dashboard
    if user:
        if user.person_type != "customer":
            logger.debug(f"Non-customer user ({user.person_type}) redirected from home to dashboard")
            return RedirectResponse(url="/dashboard", status_code=303)
        
        logger.debug(f"Customer user accessing home page")
        return templates.TemplateResponse("home.html", {"request": request, "user": user})
    
    # For non-logged in users, show the home page
    logger.debug("Non-logged in user accessing home page")
    return templates.TemplateResponse("home.html", {"request": request, "user": None})