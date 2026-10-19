import io
import pytest
from decimal import Decimal
from backend.app.services.upload_service import UploadService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.matching_service import MatchingService
from backend.app.schemas.upload import UploadInitiateRequest
from backend.app.models.base import Match


@pytest.mark.integration
def test_matching_funnel_and_idempotency(db_session, test_settings):
    upload_svc = UploadService(db_session, test_settings)
    upload_res = upload_svc.initiate_upload(UploadInitiateRequest(
        filename="matching_test.csv", content_type="text/csv", size_bytes=1000
    ))
    import_id = upload_res.import_id

    csv_data = """user_id,name,email,monthly_income,credit_score,employment_status,age
u-rich-salaried,Rich Person,rich@example.com,150000,800,Salaried,35
u-low-credit,Low Credit,low@example.com,50000,600,Salaried,30
u-self-emp,Self Employed,self@example.com,70000,740,Self-Employed,40
"""
    ingestion_svc = IngestionService(db_session, test_settings)
    ingestion_svc.process_csv_stream(import_id, io.StringIO(csv_data))

    matching_svc = MatchingService(db_session, test_settings)
    metrics = matching_svc.execute_matching_funnel(import_id)

    assert metrics.users_evaluated == 3
    assert metrics.theoretical_pairs == 3 * 6  # 18 pairs
    assert metrics.pairs_after_sql_prefilter > 0
    assert metrics.sql_reduction_percentage > 0

    first_run_matches = db_session.query(Match).filter(Match.import_id == import_id).count()
    assert first_run_matches > 0

    # Test Idempotency: re-executing matching funnel must not insert duplicate matches
    matching_svc.execute_matching_funnel(import_id)
    second_run_matches = db_session.query(Match).filter(Match.import_id == import_id).count()
    assert second_run_matches == first_run_matches
