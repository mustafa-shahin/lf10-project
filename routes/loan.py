from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Application, Person
from routes.utils import get_db, require_login
from routes.calculations import calculate_dscr, calculate_ccr, get_bonitaet_score

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def validate_immediate_loan(loan_subtype, requested_amount, repayment_amount, term_in_years):
    if requested_amount > 40000:
        raise ValueError("Bei Sofortkrediten darf der angefragte Betrag 40.000 € nicht überschreiten.")
    if loan_subtype == "tilgung":
        if repayment_amount <= 0:
            raise ValueError("Bitte geben Sie eine gültige Tilgungshöhe an.")
        calc_term = requested_amount / repayment_amount
        if calc_term > 5:
            raise ValueError("Die Laufzeit für ein Tilgungsdarlehen darf 5 Jahre nicht überschreiten.")
        return int(calc_term)
    else:
        if term_in_years <= 0:
            raise ValueError("Bitte geben Sie eine gültige Laufzeit ein.")
        return term_in_years
    
def validate_building_loan(loan_subtype, term_in_years):
    if loan_subtype != "annuitaet":
        raise ValueError("Bei Baufinanzierungen ist ausschließlich ein Annuitätendarlehen möglich.")
    if term_in_years <= 0:
        raise ValueError("Bitte geben Sie eine gültige Laufzeit ein.")
    if term_in_years > 20:
        raise ValueError("Die Laufzeit für eine Baufinanzierung darf 20 Jahre nicht überschreiten.")
    return term_in_years


@router.get("/loan", response_class=HTMLResponse)
def get_loan_form(request: Request, user: Person = Depends(require_login)):
    return templates.TemplateResponse(
        "loan.html",
        {
            "request": request,
            "person_identifier": user.id,
            "user": user
        }
    )

@router.post("/loan_submit", response_class=HTMLResponse)
def loan_submit(
    request: Request,
    loan_type: str = Form(...),
    loan_subtype: str = Form(...),
    requested_amount: int = Form(...),
    repayment_amount: int = Form(0),
    term_in_years: int = Form(0),

    available_income: float = Form(...),
    total_debt_payments: float = Form(...),
    collateral_value: float = Form(...),
    total_outstanding_debt: float = Form(...),

    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    # Validate the loan constraints
    try:
        if loan_type == "immediate":
            final_term = validate_immediate_loan(
                loan_subtype,
                requested_amount,
                repayment_amount,
                term_in_years
            )
            type_str = "Sofortkredit"
        elif loan_type == "building":
            final_term = validate_building_loan(
                loan_subtype,
                term_in_years
            )
            type_str = "Baufinanzierung"
        else:
            raise ValueError("Ungültige Darlehensart.")
    except ValueError as e:
        # If constraints fail, show a rejection page
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "user": user,
                "rejected": True,
                "rejected_reason": str(e),
            }
        )

    # Calculate DSCR / CCR
    dscr_value = calculate_dscr(available_income, total_debt_payments)
    ccr_value = calculate_ccr(collateral_value, total_outstanding_debt)
    bonitaet_rating = get_bonitaet_score()

    new_app = Application(
        person_id=user.id,
        loan_type=type_str,
        loan_subtype=loan_subtype,
        requested_amount=requested_amount,
        term_in_years=final_term,
        repayment_amount=repayment_amount,
        status="in bearbeitung",
        available_income=available_income,
        total_debt_payments=total_debt_payments,
        collateral_value=collateral_value,
        total_outstanding_debt=total_outstanding_debt,
        dscr=dscr_value,
        ccr=ccr_value,
        bonitaet=bonitaet_rating
    )

    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    # OPTIONAL: Auto-reject logic based on DSCR/CCR thresholds
    if dscr_value < 1.0 or ccr_value < 1.0:
        new_app.status = "abgelehnt"
        db.commit()
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "user": user,
                "rejected": True,
                "rejected_reason": (
                    f"Bonitätsprüfung negativ (DSCR={dscr_value:.2f}, "
                    f"CCR={ccr_value:.2f}). Antrag abgelehnt."
                ),
            }
        )

    return RedirectResponse(url=f"/upload?application_id={new_app.id}", status_code=303)
