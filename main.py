import os
import sass
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from routes.admin import router as admin_router
from db import init_db
from routes.utils import get_db, get_current_user 
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.loan import router as loan_router
from routes.files import router as files_router

app = FastAPI()

@app.on_event("startup")
def on_startup():
    if os.path.exists("static/scss"):
        sass.compile(dirname=("static/scss", "static/css"), output_style="compressed")
    init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(loan_router)
app.include_router(files_router)
app.include_router(admin_router)
@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    else:
        return RedirectResponse(url="/login")
