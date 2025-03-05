from typing import List
from fastapi import APIRouter, Depends, Request, HTTPException, Form, UploadFile, File as FastAPIFile
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models import Application, File, Person
from routes.utils import get_db, require_login

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/upload", response_class=HTMLResponse)
def get_upload(
    request: Request,
    application_id: int,
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj or app_obj.person_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found or not yours.")

    files = db.query(File).filter_by(application_id=app_obj.id).all()
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "person_identifier": user.id,
            "application_id": application_id,
            "temp_files": files
        }
    )

@router.post("/upload_temp")
async def upload_temp(
    application_id: int = Form(...),
    files: List[UploadFile] = FastAPIFile(...),
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj or app_obj.person_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found or not yours.")

    new_files = []
    for upload in files:
        file_data = await upload.read()
        file_record = File(
            file_name=upload.filename,
            file_type=upload.content_type.lower(),
            file_data=file_data,
            person_id=user.id,
            application_id=app_obj.id
        )
        db.add(file_record)
        db.flush()
        new_files.append({"id": file_record.id, "file_name": file_record.file_name})

    db.commit()
    return JSONResponse({"files": new_files})

@router.get("/download/{file_id}")
def download_file(
    file_id: int,
    request: Request,
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found.") 
    if user.person_type != "employee":
        if file_record.person_id != user.id:
         raise HTTPException(status_code=403, detail="Not allowed.")

    headers = {"Content-Disposition": f'attachment; filename="{file_record.file_name}"'}
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
    file_obj = db.query(File).filter(File.id == file_id).first()
    if not file_obj or file_obj.person_id != user.id:
        raise HTTPException(status_code=404, detail="File not found or not yours.")

    db.delete(file_obj)
    db.commit()
    return {"detail": f"File {file_id} deleted successfully."}
