import random
import logging
logger = logging.getLogger(__name__)

class LoanDecision:
    def __init__(self, boni_score: float, dscr: float, ccr: float, loan_type: str):
        self.boni_score = boni_score
        self.dscr = dscr
        self.ccr = ccr
        self.loan_type = loan_type
        self.decision = None
        self.reason = None

    @staticmethod
    def calculate_dscr(available_income: float, total_debt_payments: float, requested_amount: float, term_in_years: int, interest_rate: float = 0.05) -> float:

         # Calculate monthly payment for the new loan (annuity formula)
        monthly_interest_rate = interest_rate / 12
        total_payments = term_in_years * 12
        
        # Calculate monthly payment using the annuity 
        if total_payments > 0 and monthly_interest_rate > 0:
            monthly_loan_payment = requested_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments) / ((1 + monthly_interest_rate) ** total_payments - 1)
        else:
            monthly_loan_payment = requested_amount / total_payments if total_payments > 0 else 0
        
        #formula source for the fomula: https://stackoverflow.com/questions/48780465/loan-repayment-calculation-in-python
        # Add the new loan payment to existing debt payments
        total_monthly_payments = total_debt_payments / 12 + monthly_loan_payment
        
        # Calculate DSCR
        dscr = available_income  / total_monthly_payments if total_monthly_payments > 0 else float('inf')
        
        logger.debug(f"DSCR calculation: income={available_income }, total_payments={total_monthly_payments}, dscr={dscr}")
        return dscr

    @staticmethod
    def calculate_ccr(collateral_value: float, total_outstanding_debt: float, requested_amount: float) -> float:
        # Add the new loan to existing debt
        total_debt = total_outstanding_debt + requested_amount
        
        # Calculate CCR
        ccr = collateral_value / total_debt if total_debt > 0 else float('inf')
        
        logger.debug(f"CCR calculation: collateral={collateral_value}, total_debt={total_debt}, ccr={ccr}")
        return ccr

    @staticmethod
    def get_bonitaet_score() -> float:
        random.seed(42) 
        return  669#round(random.uniform(550, 650), 2)

    def evaluate(self):       
        logger.info(f"Evaluating loan application: type={self.loan_type}, boni={self.boni_score}, dscr={self.dscr}, ccr={self.ccr}")
        
        if self.boni_score < 579:
            return self._reject("Boni zu niedrig")

        loan_checks = {
            "Sofortkredit": self._check_sofortkredit,
            "Baudarlehen": self._check_baudarlehen
        }
        check_method = loan_checks.get(self.loan_type, self._unknown_loan_type)
        return check_method()

    def _check_sofortkredit(self):
        return self._approve("Sofortkredit genehmigt")

    def _check_baudarlehen(self):
    
        # If DSCR < 1: Reject
        # If DSCR >= 2 and CCR >= 0.75: Approve
        # If DSCR >= 1 and < 2 and CCR >= 1: Approve
        # If DSCR >= 1 and < 2 and CCR < 1: Pending (additional security needed)
        #- If DSCR >= 2 and CCR < 0.75: Pending (additional security needed)
        
        if self.dscr < 1:
            return self._reject("DSCR zu niedrig für Baudarlehen (< 1)")
        
        if self.dscr >= 2 and self.ccr >= 0.75:
            return self._approve("Baudarlehen genehmigt (DSCR >= 2, CCR >= 0.75)")
        
        if 1 <= self.dscr < 2 and self.ccr >= 1:
            return self._approve("Baudarlehen genehmigt (1 <= DSCR < 2, CCR >= 1)")
        
        if (1 <= self.dscr < 2 and self.ccr < 1) or (self.dscr >= 2 and self.ccr < 0.75):
            return self._pending("Zusätzliche Sicherheit erforderlich (1 Monat Verzögerung)")
        
        return self._reject("Ungenügende DSCR oder CCR Werte")

    def _unknown_loan_type(self):
        return self._reject("Unbekannter Kredittyp")

    def _approve(self, reason):
        self.decision = "approved"
        self.reason = reason
        return self.get_result()

    def _reject(self, reason):
        self.decision = "rejected"
        self.reason = reason
        return self.get_result()

    def _pending(self, reason):
        self.decision = "pending"
        self.reason = reason
        return self.get_result()

    def get_result(self):
        return {"decision": self.decision, "reason": self.reason}