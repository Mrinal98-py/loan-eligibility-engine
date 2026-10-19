#!/usr/bin/env python3
"""
Seed verified public loan products from major institutions into PostgreSQL.
"""
import os
import sys
from decimal import Decimal

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal
from backend.app.repositories.product_repo import LoanProductRepository

PRODUCTS = [
    {
        "source_name": "HDFC Bank",
        "source_url": "https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan",
        "product_name": "HDFC Bank Personal Loan for Salaried",
        "product_type": "Personal Loan",
        "interest_rate_min": Decimal("10.50"),
        "interest_rate_max": Decimal("21.00"),
        "min_monthly_income": Decimal("25000.00"),
        "min_credit_score": 720,
        "max_credit_score": None,
        "min_age": 21,
        "max_age": 60,
        "eligible_employment_statuses": ["Salaried"],
        "eligibility_criteria_raw": "Salaried employees aged 21-60 with net monthly income >= Rs 25,000 and credit score >= 720",
        "eligibility_evidence": {
            "income_evidence": "Published net monthly income >= 25,000",
            "score_evidence": "Preferred CIBIL score 720+",
            "age_evidence": "Min 21, Max 60 at maturity"
        },
        "is_active": True,
    },
    {
        "source_name": "State Bank of India",
        "source_url": "https://sbi.co.in/web/personal-banking/loans/personal-loans/xpress-credit",
        "product_name": "SBI Xpress Credit Personal Loan",
        "product_type": "Personal Loan",
        "interest_rate_min": Decimal("11.15"),
        "interest_rate_max": Decimal("14.30"),
        "min_monthly_income": Decimal("30000.00"),
        "min_credit_score": 700,
        "max_credit_score": None,
        "min_age": 21,
        "max_age": 58,
        "eligible_employment_statuses": ["Salaried"],
        "eligibility_criteria_raw": "Salaried employees earning >= Rs 30,000 with CIBIL score >= 700",
        "eligibility_evidence": {
            "income_evidence": "Minimum net monthly income Rs 30,000",
            "score_evidence": "Minimum credit score 700 required"
        },
        "is_active": True,
    },
    {
        "source_name": "ICICI Bank",
        "source_url": "https://www.icicibank.com/personal-banking/loans/personal-loan",
        "product_name": "ICICI Bank Flexible Personal Loan",
        "product_type": "Personal Loan",
        "interest_rate_min": Decimal("10.80"),
        "interest_rate_max": Decimal("16.50"),
        "min_monthly_income": Decimal("35000.00"),
        "min_credit_score": 700,
        "max_credit_score": None,
        "min_age": 23,
        "max_age": 58,
        "eligible_employment_statuses": ["Salaried", "Self-Employed"],
        "eligibility_criteria_raw": "Salaried and self-employed professionals with minimum monthly income Rs 35,000 and credit score 700+",
        "eligibility_evidence": {
            "income_evidence": "Minimum net take-home salary Rs 35,000 p.m.",
            "score_evidence": "CIBIL score 700 or above"
        },
        "is_active": True,
    },
    {
        "source_name": "Bajaj Finserv",
        "source_url": "https://www.bajajfinserv.in/personal-loan",
        "product_name": "Bajaj Finserv Instant Personal Loan",
        "product_type": "Personal Loan",
        "interest_rate_min": Decimal("11.00"),
        "interest_rate_max": Decimal("22.00"),
        "min_monthly_income": Decimal("35000.00"),
        "min_credit_score": 685,
        "max_credit_score": None,
        "min_age": 21,
        "max_age": 68,
        "eligible_employment_statuses": ["Salaried", "Business", "Self-Employed"],
        "eligibility_criteria_raw": "Indian citizens aged 21-68, salaried or self-employed, monthly salary >= Rs 35,000, credit score >= 685",
        "eligibility_evidence": {
            "income_evidence": "Monthly salary starting from Rs 35,000",
            "score_evidence": "CIBIL score of 685 or higher"
        },
        "is_active": True,
    },
    {
        "source_name": "Axis Bank",
        "source_url": "https://www.axisbank.com/retail/loans/personal-loan",
        "product_name": "Axis Bank Business & Self-Employed Loan",
        "product_type": "Personal Loan",
        "interest_rate_min": Decimal("12.00"),
        "interest_rate_max": Decimal("21.00"),
        "min_monthly_income": Decimal("50000.00"),
        "min_credit_score": 725,
        "max_credit_score": None,
        "min_age": 24,
        "max_age": 65,
        "eligible_employment_statuses": ["Self-Employed", "Business"],
        "eligibility_criteria_raw": "Self-employed individuals and business owners with declared monthly income >= Rs 50,000 and credit score >= 725",
        "eligibility_evidence": {
            "income_evidence": "Minimum monthly income Rs 50,000 based on ITR",
            "score_evidence": "Score >= 725"
        },
        "is_active": True,
    },
    {
        "source_name": "Kotak Mahindra Bank",
        "source_url": "https://www.kotak.com/en/personal-banking/loans/personal-loan.html",
        "product_name": "Kotak Premium Personal Loan",
        "product_type": "Personal Loan",
        "interest_rate_min": Decimal("10.99"),
        "interest_rate_max": Decimal("18.00"),
        "min_monthly_income": Decimal("40000.00"),
        "min_credit_score": 750,
        "max_credit_score": None,
        "min_age": 21,
        "max_age": 60,
        "eligible_employment_statuses": ["Salaried"],
        "eligibility_criteria_raw": "Salaried corporate employees with net income >= Rs 40,000 and credit score >= 750",
        "eligibility_evidence": {
            "income_evidence": "Minimum net monthly salary Rs 40,000",
            "score_evidence": "Credit score 750+"
        },
        "is_active": True,
    }
]


def seed():
    db = SessionLocal()
    try:
        repo = LoanProductRepository(db)
        print("Seeding verified loan products...")
        for p in PRODUCTS:
            saved = repo.upsert_product(p)
            print(f"  + Seeded: {saved.product_name} ({saved.source_name})")
        print("Product seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
