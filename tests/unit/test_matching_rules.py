import pytest
from decimal import Decimal
from backend.app.services.matching_service import MatchingService


@pytest.mark.unit
def test_matching_rule_evaluation_success():
    svc = MatchingService(db=None)
    candidate_row = {
        "monthly_income": Decimal("75000"),
        "min_monthly_income": Decimal("30000"),
        "credit_score": 740,
        "min_credit_score": 700,
        "max_credit_score": None,
        "age": 35,
        "min_age": 21,
        "max_age": 60,
        "employment_status": "Salaried",
        "eligible_employment_statuses": ["Salaried"],
        "eligibility_evidence": {
            "income_evidence": "Min 30k",
            "score_evidence": "Min 700",
            "age_evidence": "21-60"
        }
    }
    is_eligible, reasons = svc._evaluate_candidate_pair(candidate_row)
    assert is_eligible is True
    assert len(reasons) == 4
    criteria = {r["criterion"] for r in reasons}
    assert criteria == {"monthly_income", "credit_score", "age", "employment_status"}


@pytest.mark.unit
def test_matching_rule_fails_when_income_insufficient():
    svc = MatchingService(db=None)
    candidate_row = {
        "monthly_income": Decimal("20000"),  # Below 30000
        "min_monthly_income": Decimal("30000"),
        "credit_score": 750,
        "min_credit_score": 700,
        "max_credit_score": None,
        "age": 30,
        "min_age": 21,
        "max_age": 60,
        "employment_status": "Salaried",
        "eligible_employment_statuses": ["Salaried"],
    }
    is_eligible, reasons = svc._evaluate_candidate_pair(candidate_row)
    assert is_eligible is False
    assert len(reasons) == 0


@pytest.mark.unit
def test_matching_rule_fails_when_employment_not_eligible():
    svc = MatchingService(db=None)
    candidate_row = {
        "monthly_income": Decimal("80000"),
        "min_monthly_income": Decimal("30000"),
        "credit_score": 750,
        "min_credit_score": 700,
        "max_credit_score": None,
        "age": 30,
        "min_age": 21,
        "max_age": 60,
        "employment_status": "Business",  # Not in allowed list
        "eligible_employment_statuses": ["Salaried"],
    }
    is_eligible, reasons = svc._evaluate_candidate_pair(candidate_row)
    assert is_eligible is False
