import os
import time
import sass
from fastapi import FastAPI, Request, Depends
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
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
from routes.about_us import router as about_us_router
from routes.home import router as home_router



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SASS_IN = os.path.join(BASE_DIR, 'static', 'scss')
SASS_OUT = os.path.join(BASE_DIR, 'static', 'css')

# Watch handler
class SCSSWatchHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".scss"):
            time.sleep(1)
            recompile_scss()

def recompile_scss():
    # sass.compile(
    #     dirname=(SASS_IN, SASS_OUT),
    #     output_style="compressed"
    # )
    sass.compile(
        dirname=(SASS_IN, SASS_OUT),
        output_style="expanded"
    )

def start_scss_watcher():
    handler = SCSSWatchHandler()
    observer = Observer()
    observer.schedule(handler, path=SASS_IN, recursive=True)
    observer.start()
    return observer

app = FastAPI()

@app.on_event("startup")
def on_startup():
    init_db()
    if os.path.exists(SASS_IN):
        recompile_scss()
    global scss_observer
    scss_observer = start_scss_watcher()

@app.on_event("shutdown")
def on_shutdown():
    global scss_observer
    scss_observer.stop()
    scss_observer.join()

# main.py
app.mount("/static", StaticFiles(directory="static"), name="static_files")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(loan_router)
app.include_router(files_router)
app.include_router(admin_router)
app.include_router(about_us_router)
app.include_router(home_router)


# @app.get("/", response_class=HTMLResponse)
# def root(request: Request, db: Session = Depends(get_db)):
#     user = get_current_user(request, db)
#     if user:
#         return RedirectResponse(url="/dashboard")
#     else:
#         return RedirectResponse(url="/home")
@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user and user.person_type in ["admin", "employee"]:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/home")  
    