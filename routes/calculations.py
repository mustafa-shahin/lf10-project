import random

def calculate_dscr(available_income: float, total_debt_payments: float) -> float:
    if total_debt_payments <= 0:
        return 0.0
    return available_income / total_debt_payments


def calculate_ccr(collateral_value: float, total_outstanding_debt: float) -> float:
    if total_outstanding_debt <= 0:
        return 0.0
    return collateral_value / total_outstanding_debt


def get_bonitaet_score() -> float:
    return round(random.uniform(300, 850), 2)



