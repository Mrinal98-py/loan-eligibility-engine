import pytest
from decimal import Decimal
from backend.app.services.ingestion_service import IngestionService


@pytest.mark.unit
def test_valid_csv_row_passes():
    svc = IngestionService(db=None)
    row = {
        "user_id": "u-101",
        "name": "Arjun Das",
        "email": "arjun.das@example.com",
        "monthly_income": "65000",
        "credit_score": "740",
        "employment_status": "Salaried",
        "age": "32"
    }
    seen = set()
    validated, reason = svc.validate_row(row, 1, seen)
    assert reason is None
    assert validated is not None
    assert validated["external_user_id"] == "u-101"
    assert validated["monthly_income"] == Decimal("65000")
    assert validated["credit_score"] == 740
    assert validated["employment_status"] == "Salaried"
    assert validated["age"] == 32


@pytest.mark.unit
def test_negative_monthly_income_rejected():
    svc = IngestionService(db=None)
    row = {
        "user_id": "u-102",
        "name": "Bad Income",
        "email": "bad.income@example.com",
        "monthly_income": "-25000",
        "credit_score": "750",
        "employment_status": "Salaried",
        "age": "30"
    }
    seen = set()
    validated, reason = svc.validate_row(row, 1, seen)
    assert validated is None
    assert "Negative monthly income" in reason


@pytest.mark.unit
def test_credit_score_out_of_range_rejected():
    svc = IngestionService(db=None)
    # Sub-300
    row_low = {
        "user_id": "u-103",
        "email": "low@example.com",
        "monthly_income": "50000",
        "credit_score": "250",
        "employment_status": "Salaried",
        "age": "30"
    }
    validated, reason = svc.validate_row(row_low, 1, set())
    assert validated is None
    assert "Credit score 250 outside supported range" in reason

    # Above 900
    row_high = dict(row_low, credit_score="950")
    validated, reason = svc.validate_row(row_high, 1, set())
    assert validated is None
    assert "Credit score 950 outside supported range" in reason


@pytest.mark.unit
def test_underage_and_overage_rejected():
    svc = IngestionService(db=None)
    row_minor = {
        "user_id": "u-104",
        "email": "minor@example.com",
        "monthly_income": "50000",
        "credit_score": "700",
        "employment_status": "Salaried",
        "age": "16"
    }
    validated, reason = svc.validate_row(row_minor, 1, set())
    assert validated is None
    assert "outside legal/supported range" in reason


@pytest.mark.unit
def test_duplicate_user_id_in_file_rejected():
    svc = IngestionService(db=None)
    row1 = {
        "user_id": "u-dup-1",
        "email": "one@example.com",
        "monthly_income": "50000",
        "credit_score": "700",
        "employment_status": "Salaried",
        "age": "30"
    }
    seen = set()
    val1, err1 = svc.validate_row(row1, 1, seen)
    assert val1 is not None

    # Exact duplicate user_id
    row2 = dict(row1, email="two@example.com")
    val2, err2 = svc.validate_row(row2, 2, seen)
    assert val2 is None
    assert "Duplicate user_id 'u-dup-1'" in err2


@pytest.mark.unit
def test_invalid_email_format_rejected():
    svc = IngestionService(db=None)
    row = {
        "user_id": "u-105",
        "email": "not-a-valid-email",
        "monthly_income": "50000",
        "credit_score": "700",
        "employment_status": "Salaried",
        "age": "30"
    }
    validated, reason = svc.validate_row(row, 1, set())
    assert validated is None
    assert "Invalid email format" in reason


@pytest.mark.unit
def test_formula_injection_sanitization():
    svc = IngestionService(db=None)
    row = {
        "user_id": "u-106",
        "name": "=cmd|' /C calc'!A0",
        "email": "safe@example.com",
        "monthly_income": "50000",
        "credit_score": "700",
        "employment_status": "Salaried",
        "age": "30"
    }
    validated, reason = svc.validate_row(row, 1, set())
    assert validated is not None
    # Formula must be escaped with leading apostrophe
    assert validated["name"].startswith("'=")
