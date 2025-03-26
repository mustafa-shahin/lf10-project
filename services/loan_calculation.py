# services/loan_calculation.py
import math
import logging

logger = logging.getLogger(__name__)

class LoanCalculationService:
    @staticmethod
    def calculate_monthly_payment(principal, annual_interest_rate, term_years):
        try:
            # Convert annual interest rate to monthly rate and decimal form
            monthly_interest_rate = annual_interest_rate / 100 / 12
            
            # Number of monthly payments
            num_payments = term_years * 12
            
            # Handle edge case of 0% interest
            if annual_interest_rate == 0:
                return principal / num_payments
            
            factor = math.pow(1 + monthly_interest_rate, num_payments)
            monthly_payment = principal * (monthly_interest_rate * factor) / (factor - 1)
            
            return round(monthly_payment, 2)
        except Exception as e:
            logger.error(f"Error calculating monthly payment: {str(e)}")
            return None
    
    @staticmethod
    def calculate_total_payments(monthly_payment, term_years):
        try:
            num_payments = term_years * 12
            return round(monthly_payment * num_payments, 2)
        except Exception as e:
            logger.error(f"Error calculating total payments: {str(e)}")
            return None
    
    @staticmethod
    def calculate_total_interest(principal, total_payments):
        try:
            return round(total_payments - principal, 2)
        except Exception as e:
            logger.error(f"Error calculating total interest: {str(e)}")
            return None
    
    @staticmethod
    def create_amortization_schedule(principal, annual_interest_rate, term_years):
        try:
            monthly_payment = LoanCalculationService.calculate_monthly_payment(
                principal, annual_interest_rate, term_years
            )
            
            # Convert annual interest rate to monthly rate in decimal form
            monthly_interest_rate = annual_interest_rate / 100 / 12
            
            remaining_balance = principal
            schedule = []
            
            for month in range(1, term_years * 12 + 1):
                # Calculate interest for this month
                interest_payment = remaining_balance * monthly_interest_rate
                
                # Calculate principal for this month
                principal_payment = monthly_payment - interest_payment
                
                # Update remaining balance
                remaining_balance -= principal_payment
                
                # Ensure the final balance is exactly 0 (handle floating point errors)
                if month == term_years * 12:
                    principal_payment = monthly_payment - interest_payment
                    remaining_balance = 0
                
                # Add payment info to schedule
                schedule.append({
                    "month": month,
                    "payment": round(monthly_payment, 2),
                    "principal": round(principal_payment, 2),
                    "interest": round(interest_payment, 2),
                    "remaining_balance": round(max(0, remaining_balance), 2)
                })
            
            return schedule
        except Exception as e:
            logger.error(f"Error creating amortization schedule: {str(e)}")
            return []

loan_calculation_service = LoanCalculationService()