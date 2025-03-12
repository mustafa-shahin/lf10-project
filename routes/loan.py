from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Application, Person
from routes.utils import get_db, require_login
from .calculations import LoanDecision
from datetime import datetime
from typing import Optional
router = APIRouter()
templates = Jinja2Templates(directory="templates")
bonitaet_rating = LoanDecision.get_bonitaet_score()

def validate_boni_score(boni_score):
    if boni_score < 579:
        raise ValueError("Ihr Bonitätsscore ist zu niedrig für eine Kreditvergabe.")

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
        elif term_in_years > 5:
            raise ValueError("Die Laufzeit für ein Annuitätendarlehen darf 5 Jahre nicht überschreiten.")
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
def get_loan_form(request: Request, user: Person = Depends(require_login), loan_type: str = None):
    return templates.TemplateResponse(
        "loan.html",
        {
            "request": request,
            "person_identifier": user.id,
            "user": user,
              "loan_type": loan_type
            
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
    available_income: Optional[float] = Form(None),
    total_debt_payments: Optional[float] = Form(None),
     collateral_value: Optional[float] = Form(None),
    total_outstanding_debt: Optional[float] = Form(None),
    user: Person = Depends(require_login),
    db: Session = Depends(get_db)
):
    try:
        if loan_type == "Sofortkredit":
            final_term = validate_immediate_loan(loan_subtype, requested_amount, repayment_amount, term_in_years)
            type_str = "Sofortkredit"
        elif loan_type == "Baudarlehen":
            final_term = validate_building_loan(loan_subtype, term_in_years)
            type_str = "Baudarlehen"
        else:
            raise ValueError("Ungültige Darlehensart.")

        validate_boni_score(bonitaet_rating)
    except ValueError as e:
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "user": user,
                "rejected": True,
                "rejected_reason": str(e),
            }
        )

    if loan_type == "Baudarlehen":
        dscr_value = LoanDecision.calculate_dscr(available_income, total_debt_payments, requested_amount, final_term)
        ccr_value = LoanDecision.calculate_ccr(collateral_value, total_outstanding_debt, requested_amount)
    else:
        dscr_value = 0.0
        ccr_value = 0.0

    decision_obj = LoanDecision(
        boni_score=bonitaet_rating,
        dscr=dscr_value,
        ccr=ccr_value,
        loan_type=type_str
    )
    result = decision_obj.evaluate()
    new_app = Application(
        person_id=user.id,
        loan_type=type_str,
        loan_subtype=loan_subtype,
        requested_amount=requested_amount,
        term_in_years=final_term,
        repayment_amount=repayment_amount,
        status="in bearbeitung",
        dscr=dscr_value,
        ccr=ccr_value,
        bonitaet=bonitaet_rating,
        decision=result["decision"],
        reason=result["reason"],
        decided_at=datetime.utcnow()
    )

    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return RedirectResponse(url=f"/upload?application_id={new_app.id}", status_code=303)
