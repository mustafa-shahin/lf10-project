import random

class LoanDecision:
    def __init__(self, boni_score: float, dscr: float, ccr: float, loan_type: str):
        self.boni_score = boni_score
        self.dscr = dscr
        self.ccr = ccr
        self.loan_type = loan_type
        self.decision = None
        self.reason = None

    @staticmethod
    def calculate_dscr(available_income: float, total_debt_payments: float, requested_amount:float, term_in_years:int ) -> float:
        total_debt_payments += requested_amount / term_in_years
        return available_income * 12/ total_debt_payments if total_debt_payments > 0 else 0.0

    @staticmethod
    def calculate_ccr(collateral_value: float, total_outstanding_debt: float,requested_amount:float) -> float:
        total_outstanding_debt  += requested_amount 
        return collateral_value / total_outstanding_debt if total_outstanding_debt > 0 else 0.0

    @staticmethod
    def get_bonitaet_score() -> float:
        random.seed(42)
        random_numbers = [round(random.uniform(550, 650), 2) for _ in range(5)]
        return random.choice(random_numbers)

    def evaluate(self):
        if self.boni_score < 579:
            return self._reject("Boni zu niedrig")

        loan_checks = {
            "Sofortkredit": self._check_sofortkredit,
            "Baudarlehen": self._check_baudarlehen
        }
        check_method = loan_checks.get(self.loan_type, self._unknown_loan_type)
        return check_method()

    def _check_sofortkredit(self):
        # DSCR and CCR are not used for Sofortkredit.
        return self._approve("Sofortkredit genehmigt")

    def _check_baudarlehen(self):
        if self.dscr < 1:
            return self._reject("DSCR zu niedrig für Baudarlehen")
        if (1 <= self.dscr < 2 and self.ccr < 1) or (self.dscr >= 2 and self.ccr < 0.75):
            return self._pending("Zusätzliche Sicherheit erforderlich (1 Monat Verzögerung)")
        return self._approve("Baudarlehen genehmigt")

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
        self.decision = "ausstehend"
        self.reason = reason
        return self.get_result()

    def get_result(self):
        return {"decision": self.decision, "reason": self.reason}
