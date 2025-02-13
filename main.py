import os
import uuid
import sass
from typing import List
from fastapi import FastAPI, Request, Form, UploadFile, File as FastAPIFile, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import SessionLocal, init_db
from models import Person, Application, File as FileModel

# -------------------------------------------------------------------------
# In-memory storage until user finalizes
# -------------------------------------------------------------------------
temp_data = {}

app = FastAPI()

@app.on_event("startup")
def compile_scss():
    if os.path.exists("static/scss"):
        sass.compile(dirname=("static/scss", "static/css"), output_style="compressed")

app.mount("/static", StaticFiles(directory="static"), name="static_files")
templates = Jinja2Templates(directory="templates")

# -------------------------------------------------------------------------
# 1) Person Form
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    """Display form.html for Person data."""
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/submit_person", response_class=HTMLResponse)
def submit_person(
    request: Request,
    salutation: str = Form(...),
    title: str = Form(None),
    first_name: str = Form(...),
    second_name: str = Form(...),
    street: str = Form(...),
    house_number: str = Form(...),
    zip_code: str = Form(...),
    city: str = Form(...),
    country: str = Form(...),
):
    """Store person data in memory and redirect to loan page."""
    person_identifier = str(uuid.uuid4())
    temp_data[person_identifier] = {
        "person_data": {
            "salutation": salutation,
            "title": title,
            "first_name": first_name,
            "second_name": second_name,
            "street": street,
            "house_number": house_number,
            "zip_code": zip_code,
            "city": city,
            "country": country,
        },
        "loan_data": {},
        "files": []
    }
    return RedirectResponse(
        url=f"/loan?person_identifier={person_identifier}",
        status_code=303
    )

# -------------------------------------------------------------------------
# 2) Loan Form & Logic
# -------------------------------------------------------------------------
@app.get("/loan", response_class=HTMLResponse)
def get_loan_form(request: Request, person_identifier: str):
    """Show loan.html"""
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return templates.TemplateResponse("loan.html", {
        "request": request,
        "person_identifier": person_identifier
    })

@app.post("/loan_submit", response_class=HTMLResponse)
def loan_submit(
    request: Request,
    loan_type: str = Form(...),
    loan_subtype: str = Form(...),
    requested_amount: int = Form(...),
    repayment_amount: int = Form(0),
    term_in_years: int = Form(0),
    person_identifier: str = Form(...),
):
    """Perform loan validation, reject if invalid, otherwise proceed."""
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Save loan data
    temp_data[person_identifier]["loan_data"] = {
        "loan_type": loan_type,
        "loan_subtype": loan_subtype,
        "requested_amount": requested_amount,
        "repayment_amount": repayment_amount,
        "user_term": term_in_years
    }

    def reject(reason: str):
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "rejected": True,
                "rejected_reason": reason
            }
        )

    if loan_type == "immediate" and requested_amount > 40000:
        return reject("Der Kredit übersteigt den Höchstbetrag (40.000) für Sofortkredite..")

    final_term = term_in_years if term_in_years > 0 else 1  # Ensures non-null
    if loan_type == "building" and final_term > 20:
        return reject("Building loan term exceeds 20 years.")

    temp_data[person_identifier]["loan_data"]["final_term"] = final_term
    return RedirectResponse(
        url=f"/upload?person_identifier={person_identifier}",
        status_code=303
    )

# -------------------------------------------------------------------------
# 3) File Upload + Deletion
# -------------------------------------------------------------------------
@app.get("/upload", response_class=HTMLResponse)
def get_upload(request: Request, person_identifier: str):
    """Show file upload page."""
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "person_identifier": person_identifier,
            "temp_files": temp_data[person_identifier]["files"]
        }
    )

@app.post("/upload_temp")
async def upload_temp(
    request: Request,
    person_identifier: str = Form(...),
    files: List[UploadFile] = FastAPIFile(...),
):
    """Store files temporarily before DB commit."""
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    new_files = []
    for upload in files:
        file_id = str(uuid.uuid4())
        file_record = {
            "id": file_id,
            "file_name": upload.filename,
            "content_type": upload.content_type.lower(),
            "data": await upload.read()
        }
        temp_data[person_identifier]["files"].append(file_record)
        new_files.append({"id": file_id, "file_name": upload.filename})

    return JSONResponse({"files": new_files})

@app.delete("/file/{file_id}")
def delete_file(file_id: str, person_identifier: str = Query(...)):
    """Delete a file from memory."""
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    files_list = temp_data[person_identifier]["files"]
    for i, f in enumerate(files_list):
        if f["id"] == file_id:
            files_list.pop(i)
            return {"detail": f"File {file_id} deleted successfully."}

    raise HTTPException(status_code=404, detail="File not found.")

# -------------------------------------------------------------------------
# 4) Final DB Commit
# -------------------------------------------------------------------------
@app.get("/create_db_records", response_class=HTMLResponse)
def create_db_records(request: Request, person_identifier: str):
    """Save Person, Application, and Files to DB."""
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    init_db()
    db = SessionLocal()
    try:
        # 1) Create Person
        person_data = temp_data[person_identifier]["person_data"]
        new_person = Person(**person_data)
        db.add(new_person)
        db.flush()  # get new_person.id

        loan_data = temp_data[person_identifier]["loan_data"]
        new_app = Application(
            person_id=new_person.id,
            loan_type=loan_data["loan_type"],
            loan_subtype=loan_data["loan_subtype"],
            requested_amount=loan_data["requested_amount"],
            term_in_years=loan_data["final_term"]
        )
        db.add(new_app)
        db.flush()  # get new_app.id

        # 3) Store Files, linking them to the new Application
        for f in temp_data[person_identifier]["files"]:
            new_file = FileModel(
                file_name=f["file_name"],
                file_type=f["content_type"],
                file_data=f["data"],
                person_id=new_person.id,
                application_id=new_app.id
            )
            db.add(new_file)

        db.commit()
    finally:
        db.close()

    # Clear temp data for this user
    del temp_data[person_identifier]

    return templates.TemplateResponse("upload_success.html", {
        "request": request,
        "rejected": False
    })
