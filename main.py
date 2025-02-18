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
init_db()
app.mount("/static", StaticFiles(directory="static"), name="static_files")
templates = Jinja2Templates(directory="templates")

# -------------------------------------------------------------------------
# 1) Person Form
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/submit_person", response_class=HTMLResponse)
def submit_person(
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
    #store person data in memory and redirect to loan page
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
# 2) Loan Form & Validation Helpers
# -------------------------------------------------------------------------

def validate_immediate_loan(
    loan_subtype: str,
    requested_amount: int,
    repayment_amount: int,
    term_in_years: int
) -> int:
    #Validierung eines Sofortkredits; gibt die endgültige Laufzeit zurück, wenn gültig,
    if requested_amount > 40000:
        raise ValueError("Bei Sofortkrediten darf der angefragte Betrag 40.000 € nicht überschreiten.")

    if loan_subtype == "tilgung":
        if repayment_amount <= 0:
            raise ValueError("Bitte geben Sie eine gültige Tilgungshöhe an.")
        calculated_term = requested_amount / repayment_amount
        if calculated_term > 5:
            raise ValueError("Die Laufzeit für ein Tilgungsdarlehen darf 5 Jahre nicht überschreiten.")
        return int(calculated_term)
    else:
        if term_in_years <= 0:
            raise ValueError("Bitte geben Sie eine gültige Laufzeit ein.")
        return term_in_years

def validate_building_loan(
    loan_subtype: str,
    term_in_years: int
) -> int:
    if loan_subtype != "annuitaet":
        raise ValueError("Bei Baufinanzierungen ist ausschließlich ein Annuitätendarlehen möglich.")
    if term_in_years <= 0:
        raise ValueError("Bitte geben Sie eine gültige Laufzeit ein.")
    if term_in_years > 20:
        raise ValueError("Die Laufzeit für eine Baufinanzierung darf 20 Jahre nicht überschreiten.")
    return term_in_years


@app.get("/loan", response_class=HTMLResponse)
def get_loan_form(request: Request, person_identifier: str):
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    return templates.TemplateResponse(
        "loan.html",
        {
            "request": request,
            "person_identifier": person_identifier
        }
    )

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
    #Darlehensvalidierung durchführen, bei Ungültigkeit ablehnen, sonst weiter zur Upload-Seite.
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    def reject(reason: str):
        #helper function to show rejection page with reason.
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "rejected": True,
                "rejected_reason": reason
            }
        )

    # Prepare loan data
    loan_data = {
        "loan_type": loan_type,
        "loan_subtype": loan_subtype,
        "requested_amount": requested_amount,
        "repayment_amount": repayment_amount,
        "user_term": term_in_years,
    }

    # Validate
    try:
        if loan_type == "immediate":
            final_term = validate_immediate_loan(
                loan_subtype,
                requested_amount,
                repayment_amount,
                term_in_years
            )
        elif loan_type == "building":
            final_term = validate_building_loan(
                loan_subtype,
                term_in_years
            )
        else:
            raise ValueError("Ungültige Darlehensart.")

    except ValueError as e:
        # If validation fails, show rejection page
        return reject(str(e))

    # If validation passed, store final term
    loan_data["final_term"] = final_term
    temp_data[person_identifier]["loan_data"] = loan_data

    return RedirectResponse(
        url=f"/upload?person_identifier={person_identifier}",
        status_code=303
    )

# -------------------------------------------------------------------------
# 3) File Upload + Deletion
# -------------------------------------------------------------------------
@app.get("/upload", response_class=HTMLResponse)
def get_upload(request: Request, person_identifier: str):
    #show file upload page.
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
    person_identifier: str = Form(...),
    files: List[UploadFile] = FastAPIFile(...),
):
    #store files temporarily before DB commit.
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
#Delete a file from memory
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
    if person_identifier not in temp_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    db = SessionLocal()
    try:
        # Retrieve person data from temp storage
        person_data = temp_data[person_identifier]["person_data"]

        # 1) Check if the person already exists
        existing_person = db.query(Person).filter_by(**person_data).first()
        if existing_person:
            new_person = existing_person
        else:
            new_person = Person(**person_data)
            db.add(new_person)
            db.flush()  #new_person.id

        # 2) Create a new Application
        loan_data = temp_data[person_identifier]["loan_data"]
        new_app = Application(
            person_id=new_person.id,
            loan_type=loan_data["loan_type"],
            loan_subtype=loan_data["loan_subtype"],
            requested_amount=loan_data["requested_amount"],
            term_in_years=loan_data["final_term"],
            repayment_amount=loan_data["repayment_amount"]
        )
        db.add(new_app)
        db.flush()  # get new_app.id

        # 3) Store Files, linking to the same Person/Application
        for f in temp_data[person_identifier]["files"]:
            new_file = FileModel(
                file_name=f["file_name"],
                file_type=f["content_type"],
                file_data=f["data"],
                person_id=new_person.id,
                application_id=new_app.id
            )
            db.add(new_file)

        # 4) Commit
        db.commit()

    finally:
        db.close()

    # Remove from temp_data
    del temp_data[person_identifier]

    return templates.TemplateResponse(
        "upload_success.html",
        {"request": request, "rejected": False}
    )
