# main.py
import os
import time
import sass
import logging
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
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SASS_IN = os.path.join(BASE_DIR, 'static', 'scss')
SASS_OUT = os.path.join(BASE_DIR, 'static', 'css')

# Global variable for the scss observer
scss_observer = None

# SCSS Watch handler
class SCSSWatchHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".scss"):
            time.sleep(1)
            recompile_scss()

def recompile_scss():
    try:
        sass.compile(
            dirname=(SASS_IN, SASS_OUT),
            output_style="expanded"
        )
        logger.info(f"Successfully recompiled SCSS to CSS")
    except Exception as e:
        logger.error(f"Error compiling SCSS: {str(e)}")

def start_scss_watcher():
    handler = SCSSWatchHandler()
    observer = Observer()
    observer.schedule(handler, path=SASS_IN, recursive=True)
    observer.start()
    return observer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code - this runs when the application starts
    logger.info("Starting application...")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
    
    # Compile SCSS to CSS
    if os.path.exists(SASS_IN):
        try:
            recompile_scss()
        except Exception as e:
            logger.error(f"Initial SCSS compilation error: {str(e)}")
    
    # Start SCSS watcher
    global scss_observer
    scss_observer = start_scss_watcher()
    logger.info("SCSS watcher started")
    
    yield  # This is where the application runs
    
    # Shutdown code - this runs when the application stops
    logger.info("Shutting down application...")
    
    if scss_observer:
        scss_observer.stop()
        scss_observer.join()
        logger.info("SCSS watcher stopped")

# Create the FastAPI app with the lifespan context manager
app = FastAPI(title="Kreditbank Application", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static_files")

# Set up templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Include routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(loan_router)
app.include_router(files_router)
app.include_router(admin_router)
app.include_router(about_us_router)
app.include_router(home_router)

@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    # Check if user is logged in
    user = get_current_user(request, db)
    logger.debug(f"Root endpoint - User: {user.id if user else None}")
    
    if user:
        # If user is admin or employee, redirect to dashboard
        if user.person_type in ["admin", "employee"]:
            logger.debug(f"Redirecting admin/employee to dashboard")
            return RedirectResponse(url="/dashboard", status_code=303)
        # If user is customer, redirect to home
        else:
            logger.debug(f"Redirecting customer to home")
            return RedirectResponse(url="/home", status_code=303)
    else:
        # For non-logged in users, redirect to home
        logger.debug("No user found, redirecting to home")
        return RedirectResponse(url="/home", status_code=303)

@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc):
    """Custom 404 error handler"""
    logger.warning(f"404 error for URL: {request.url}")
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "error_code": 404, "message": "Seite nicht gefunden", "user": None}
    )

@app.exception_handler(500)
async def server_error_exception_handler(request: Request, exc):
    """Custom 500 error handler"""
    logger.error(f"Internal server error: {str(exc)}")
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "error_code": 500, "message": "Interner Serverfehler", "user": None}
    )

# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and their cookies"""
    logger.debug(f"Request: {request.method} {request.url}")
    
    # Log cookies (partially redacted for security)
    cookies = request.cookies
    safe_cookies = {}
    for key, value in cookies.items():
        if key == "session_id" and value:
            # Only log first few characters of session ID
            safe_cookies[key] = value[:8] + "..." if len(value) > 8 else value
        else:
            safe_cookies[key] = value
    
    logger.debug(f"Request cookies: {safe_cookies}")
    
    # Process the request
    response = await call_next(request)
    
    # Log the response status
    logger.debug(f"Response status: {response.status_code}")
    
    return response