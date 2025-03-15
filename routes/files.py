import logging
from typing import List
from fastapi import APIRouter, Depends, Request, HTTPException, Form, UploadFile, File as FastAPIFile
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models import Application, File, Person
from routes.utils import get_db, require_login

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/upload", response_class=HTMLResponse)
def get_upload(
    request: Request,
    application_id: int,
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    logger.info(f"Upload page accessed for application {application_id} by user {user.id}")
    
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found")
        raise HTTPException(status_code=404, detail="Application not found.")
        
    # Check if the user is authorized to view this application
    if app_obj.person_id != user.id and user.person_type not in ["admin", "employee"]:
        logger.warning(f"User {user.id} tried to access application {application_id} belonging to user {app_obj.person_id}")
        raise HTTPException(status_code=403, detail="You don't have permission to access this application.")

    # Get files associated with this application
    files = db.query(File).filter_by(application_id=app_obj.id).all()
    logger.debug(f"Found {len(files)} files for application {application_id}")
    
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "person_identifier": user.id,
            "application_id": application_id,
            "temp_files": files, 
            "user": user
        }
    )

@router.post("/upload_temp")
async def upload_temp(
    application_id: int = Form(...),
    files: List[UploadFile] = FastAPIFile(...),
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    logger.info(f"File upload attempt for application {application_id} by user {user.id}")
    
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        logger.warning(f"Application {application_id} not found during upload")
        raise HTTPException(status_code=404, detail="Application not found.")
        
    # Check if the user is authorized to upload to this application
    if app_obj.person_id != user.id and user.person_type not in ["admin", "employee"]:
        logger.warning(f"User {user.id} tried to upload to application {application_id} belonging to user {app_obj.person_id}")
        raise HTTPException(status_code=403, detail="You don't have permission to upload to this application.")

    new_files = []
    for upload in files:
        try:
            file_data = await upload.read()
            
            # Log file details
            logger.debug(f"Uploading file: {upload.filename}, size: {len(file_data)} bytes, type: {upload.content_type}")
            
            # Create file record
            file_record = File(
                file_name=upload.filename,
                file_type=upload.content_type.lower(),
                file_data=file_data,
                person_id=user.id,
                application_id=app_obj.id
            )
            db.add(file_record)
            db.flush()  # Get ID without committing
            
            # Add to list for response
            new_files.append({
                "id": file_record.id, 
                "file_name": file_record.file_name
            })
            
        except Exception as e:
            logger.error(f"Error uploading file {upload.filename}: {str(e)}")
            continue

    try:
        db.commit()
        logger.info(f"Successfully uploaded {len(new_files)} files to application {application_id}")
    except Exception as e:
        logger.error(f"Database error during file upload: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error saving files to database")

    return JSONResponse({"files": new_files})

@router.get("/download/{file_id}")
def download_file(
    file_id: int,
    request: Request,
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    logger.info(f"Download request for file {file_id} by user {user.id}")
    
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        logger.warning(f"File {file_id} not found")
        raise HTTPException(status_code=404, detail="File not found.")
    
    # - Admin/Employee can download any file
    # - Regular users can only download their own files
    if user.person_type not in ["admin", "employee"]:
        if file_record.person_id != user.id:
            logger.warning(f"User {user.id} tried to download file {file_id} belonging to user {file_record.person_id}")
            raise HTTPException(status_code=403, detail="You don't have permission to download this file.")

    # Set headers for the download
    headers = {"Content-Disposition": f'attachment; filename="{file_record.file_name}"'}
    
    logger.debug(f"Serving file {file_id}: {file_record.file_name}, type: {file_record.file_type}")
    
    return StreamingResponse(
        iter([file_record.file_data]),
        media_type=file_record.file_type,
        headers=headers
    )

@router.delete("/file/{file_id}")
def delete_file(
    file_id: int,
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    logger.info(f"Delete request for file {file_id} by user {user.id}")
    
    file_obj = db.query(File).filter(File.id == file_id).first()
    if not file_obj:
        logger.warning(f"File {file_id} not found during delete")
        raise HTTPException(status_code=404, detail="File not found.")
    
    # Check permissions:
    # - Admin can delete any file
    # - Regular users and employees can only delete their own files
    if user.person_type != "admin" and file_obj.person_id != user.id:
        logger.warning(f"User {user.id} tried to delete file {file_id} belonging to user {file_obj.person_id}")
        raise HTTPException(status_code=403, detail="You don't have permission to delete this file.")

    try:
        db.delete(file_obj)
        db.commit()
        logger.info(f"File {file_id} deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error during file deletion")
        
    return {"detail": f"File {file_id} deleted successfully."}