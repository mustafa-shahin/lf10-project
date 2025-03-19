import logging
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import Application, Person
from routes.utils import get_db, require_login
from services.calculations import LoanDecision
from datetime import datetime
from typing import Optional
from services.email_service import email_service

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Validation functions
def validate_boni_score(boni_score: float):
    if boni_score < 579:
        raise ValueError("Ihr Bonitätsscore ist zu niedrig für eine Kreditvergabe.")

def validate_dscr_score(dscr_score: float):
    if dscr_score < 1:
        raise ValueError("Ihr DSCR Score ist zu niedrig für eine Kreditvergabe.")

def validate_immediate_loan(loan_subtype: str, requested_amount: float, repayment_amount: float, term_in_years: int):
    if requested_amount > 40000:
        raise ValueError("Bei Sofortkrediten darf der angefragte Betrag 40.000 € nicht überschreiten.")
    
    if loan_subtype == "tilgung":
        if repayment_amount <= 0:
            raise ValueError("Bitte geben Sie eine gültige Tilgungshöhe an.")
        calc_term = requested_amount / repayment_amount / 12  # Convert to years
        if calc_term > 5:
            raise ValueError("Die Laufzeit für ein Tilgungsdarlehen darf 5 Jahre nicht überschreiten.")
        return int(calc_term)
    elif loan_subtype == "endfaellig":
        if term_in_years <= 0 or term_in_years > 5:
            raise ValueError("Die Laufzeit für ein endfälliges Darlehen muss zwischen 1 und 5 Jahren liegen.")
        return term_in_years
    else:  # annuitaet
        if term_in_years <= 0 or term_in_years > 5:
            raise ValueError("Die Laufzeit für ein Annuitätendarlehen darf 5 Jahre nicht überschreiten.")
        return term_in_years

def validate_building_loan(loan_subtype: str, term_in_years: int):
    if loan_subtype != "annuitaet":
        raise ValueError("Bei Baufinanzierungen ist ausschließlich ein Annuitätendarlehen möglich.")
    if term_in_years <= 0:
        raise ValueError("Bitte geben Sie eine gültige Laufzeit ein.")
    if term_in_years > 20:
        raise ValueError("Die Laufzeit für eine Baufinanzierung darf 20 Jahre nicht überschreiten.")
    return term_in_years

@router.get("/loan", response_class=HTMLResponse)
def get_loan_form(request: Request, user: Person = Depends(require_login), loan_type: str = None):
    # Check if user is a customer - only customers can access the loan page
    if user.person_type != "customer":
        logger.warning(f"Non-customer user (id: {user.id}, type: {user.person_type}) attempted to access loan page")
        return RedirectResponse(url="/dashboard", status_code=303)
    
    logger.info(f"Customer user {user.id} accessed loan page")
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
    # Check if user is a customer - only customers can submit loan applications
    if user.person_type != "customer":
        logger.warning(f"Non-customer user (id: {user.id}, type: {user.person_type}) attempted to submit loan application")
        raise HTTPException(status_code=403, detail="Nur Kunden können Kreditanträge stellen")
    
    logger.info(f"Customer {user.id} submitted loan application: {loan_type}, {loan_subtype}, amount: {requested_amount}")

    try:
        # Get or generate boni score (normally would come from credit bureau)
        bonitaet_rating = LoanDecision.get_bonitaet_score()
        
        # Basic validation of credit score
        validate_boni_score(bonitaet_rating)
        
        # Different validation rules based on loan type
        if loan_type == "Sofortkredit":
            final_term = validate_immediate_loan(loan_subtype, requested_amount, repayment_amount, term_in_years)
            dscr_value = 0.0  # Not used for Sofortkredit
            ccr_value = 0.0   # Not used for Sofortkredit
        elif loan_type == "Baudarlehen":
            # For building loans, validate required fields
            if not all([available_income, total_debt_payments is not None, collateral_value, total_outstanding_debt is not None]):
                logger.warning(f"Missing required fields for building loan by user {user.id}")
                raise HTTPException(
                    status_code=400, 
                    detail="Alle Felder für eine Baufinanzierung müssen ausgefüllt sein"
                )
                
            final_term = validate_building_loan(loan_subtype, term_in_years)
            
            # Calculate DSCR and CCR
            dscr_value = LoanDecision.calculate_dscr(
                available_income=float(available_income), 
                total_debt_payments=float(total_debt_payments),
                requested_amount=float(requested_amount),
                term_in_years=int(final_term)
            )
            
            ccr_value = LoanDecision.calculate_ccr(
                collateral_value=float(collateral_value),
                total_outstanding_debt=float(total_outstanding_debt),
                requested_amount=float(requested_amount)
            )
            
            # Validate DSCR
            validate_dscr_score(dscr_value)
        else:
            raise ValueError("Ungültige Darlehensart.")

        # Create decision object for evaluation
        decision_obj = LoanDecision(
            boni_score=bonitaet_rating,
            dscr=dscr_value,
            ccr=ccr_value,
            loan_type=loan_type
        )

        assignedRole = "manager" if (bonitaet_rating < 670 or dscr_value < 1.4) else "employee"
        
        # Get decision result
        result = decision_obj.evaluate()
        logger.info(f"Loan decision: {result['decision']} - {result['reason']}")
        
        # Map decision to status
        status_mapping = {
            "approved": "in bearbeitung",  # Start in processing, even if auto-approved
            "rejected": "abgelehnt",
            "pending": "in bearbeitung"
        }
        
        status = status_mapping.get(result["decision"], "in bearbeitung")
        
        # Create application record
        now = datetime.now()
        new_app = Application(
            person_id=user.id,
            loan_type=loan_type,
            loan_subtype=loan_subtype,
            requested_amount=requested_amount,
            term_in_years=final_term,
            repayment_amount=repayment_amount,
            status=status,
            dscr=dscr_value,
            ccr=ccr_value,
            bonitaet=bonitaet_rating,
            decision=result["decision"],
            reason=result["reason"],
            created_at=now,
            decided_at=now if status == "abgelehnt" else None,  # Set decided_at for rejected applications
            assignedRole = assignedRole
        )

        db.add(new_app)
        db.commit()
        db.refresh(new_app)
        
        logger.info(f"New loan application {new_app.id} created by user {user.id}")
        
        # If the application is rejected automatically, show the rejection page
        if status == "abgelehnt":
            return templates.TemplateResponse(
                "upload_success.html",
                {
                    "request": request,
                    "user": user,
                    "rejected": True,
                    "rejected_reason": result["reason"],
                }
            )
        
        # Otherwise, redirect to file upload
        return RedirectResponse(url=f"/upload?application_id={new_app.id}", status_code=303)

    except ValueError as e:
        # Handle validation errors
        logger.warning(f"Loan application validation failed for user {user.id}: {str(e)}")
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "user": user,
                "rejected": True,
                "rejected_reason": str(e),
            }
        )
    except Exception as e:
        # Handle other errors
        logger.error(f"Unexpected error in loan application: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "upload_success.html",
            {
                "request": request,
                "user": user,
                "rejected": True, 
                "rejected_reason": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
            }
        )