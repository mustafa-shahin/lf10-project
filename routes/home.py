from fastapi import Request, APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from models import Person
from routes.utils import get_db, require_login, get_current_user
from fastapi.responses import RedirectResponse
router = APIRouter()
templates = Jinja2Templates(directory="templates")

def optional_login(db: Session = Depends(get_db)) -> Optional[Person]:
    try:
        return require_login(db) 
    except Exception:
        return None 


@router.get("/home", response_class=HTMLResponse)
def get_about_us(
    request: Request,
    user: Optional[Person] = Depends(get_current_user),
    db: Session = Depends(get_db) 
):
    person = get_current_user(request, db)
    
    if person:
        if person.person_type == "customer":
            return templates.TemplateResponse("home.html", {"request": request, "user": person})
        else:
            return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("home.html", {"request": request, "user": None})

