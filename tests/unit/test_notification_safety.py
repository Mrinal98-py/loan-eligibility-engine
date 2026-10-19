import pytest
from backend.app.services.notification_service import NotificationService, NotificationSafetyError
from backend.app.settings import Settings


@pytest.mark.unit
def test_notification_safety_overrides_sample_csv_email():
    settings = Settings(
        DELIVERY_MODE="test",
        ALLOW_REAL_RECIPIENTS=False,
        TEST_EMAIL_RECIPIENTS="mytestinbox@example.com"
    )
    svc = NotificationService(db=None, settings=settings)

    # Normal sample CSV email
    sample_csv_email = "real_customer_from_csv@samplebank.com"
    resolved = svc.resolve_recipient_email(sample_csv_email)

    # Must NEVER be sent to the sample email
    assert resolved != sample_csv_email
    assert resolved == "mytestinbox@example.com"


@pytest.mark.unit
def test_notification_safety_blocks_empty_test_inbox():
    settings = Settings(
        DELIVERY_MODE="test",
        ALLOW_REAL_RECIPIENTS=False,
        TEST_EMAIL_RECIPIENTS=""
    )
    svc = NotificationService(db=None, settings=settings)

    with pytest.raises(NotificationSafetyError, match="TEST_EMAIL_RECIPIENTS is empty"):
        svc.resolve_recipient_email("sample@example.com")


@pytest.mark.unit
def test_email_body_includes_disclaimer_and_no_leak():
    settings = Settings(DELIVERY_MODE="test")
    svc = NotificationService(db=None, settings=settings)

    from backend.app.models.base import User, Match, LoanProduct
    user = User(name="Test Applicant", external_user_id="u-999")
    product = LoanProduct(
        product_name="Bank Express Loan",
        source_name="Express Bank",
        interest_rate_min=10.5,
        interest_rate_max=14.0,
        source_url="https://expressbank.test/loan"
    )
    match = Match(product=product, match_reasons=[{"message": "Income criteria passed"}])

    text_body, html_body = svc.format_email_body(user, [match])

    assert "Bank Express Loan" in text_body
    assert "Express Bank" in text_body
    assert "IMPORTANT REGULATORY DISCLAIMER" in text_body
    assert "does NOT constitute a credit offer" in text_body
    assert "DISCLAIMER" in html_body
