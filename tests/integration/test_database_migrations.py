import pytest
import uuid
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from backend.app.models.base import Import, User, LoanProduct, Match, Notification


@pytest.mark.integration
def test_import_foreign_key_cascade(db_session):
    import_rec = Import(
        original_filename="test.csv",
        object_key="uploads/test.csv"
    )
    db_session.add(import_rec)
    db_session.commit()

    user = User(
        external_user_id="u-cascade",
        import_id=import_rec.id,
        email="cascade@example.com",
        monthly_income=Decimal("50000"),
        credit_score=720,
        employment_status="Salaried",
        age=30
    )
    db_session.add(user)
    db_session.commit()

    # Deleting import must cascade delete user
    db_session.delete(import_rec)
    db_session.commit()

    remaining_user = db_session.query(User).filter(User.external_user_id == "u-cascade").first()
    assert remaining_user is None


@pytest.mark.integration
def test_prevent_duplicate_matches_constraint(db_session):
    import_rec = Import(original_filename="matches.csv", object_key="uploads/matches.csv")
    db_session.add(import_rec)
    db_session.commit()

    user = User(
        external_user_id="u-match",
        import_id=import_rec.id,
        email="match@example.com",
        monthly_income=Decimal("50000"),
        credit_score=720,
        employment_status="Salaried",
        age=30
    )
    product = db_session.query(LoanProduct).first()
    db_session.add(user)
    db_session.commit()

    m1 = Match(user_id=user.id, product_id=product.id, import_id=import_rec.id)
    db_session.add(m1)
    db_session.commit()

    # Attempt duplicate insert of same user, product, import must fail
    m2 = Match(user_id=user.id, product_id=product.id, import_id=import_rec.id)
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
