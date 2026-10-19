import io
import pytest
from backend.app.services.upload_service import UploadService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.matching_service import MatchingService
from backend.app.services.notification_service import NotificationService
from backend.app.schemas.upload import UploadInitiateRequest
from backend.app.models.base import Import, User, Match, Notification


@pytest.mark.e2e
def test_end_to_end_full_pipeline_flow(db_session, test_settings):
    """
    Complete Acceptance Test:
    Upload CSV -> Asynchronous Ingestion -> SQL Pre-filter ->
    Deterministic Rules -> Idempotent Persist -> Safe Test Notifications
    """
    # 1. Upload initiation
    upload_svc = UploadService(db_session, test_settings)
    upload_res = upload_svc.initiate_upload(UploadInitiateRequest(
        filename="e2e_users.csv",
        content_type="text/csv",
        size_bytes=1000
    ))
    import_id = upload_res.import_id
    assert import_id is not None

    # 2. Ingestion
    sample_csv = """user_id,name,email,monthly_income,credit_score,employment_status,age
e2e-user-1,Vikram Seth,vikram@originalsample.com,90000,760,Salaried,35
e2e-user-2,Kavita Rao,kavita@originalsample.com,32000,710,Salaried,29
e2e-user-3,Rajesh Khanna,rajesh@originalsample.com,18000,650,Business,45
"""
    ingestion_svc = IngestionService(db_session, test_settings)
    ingest_res = ingestion_svc.process_csv_stream(import_id, io.StringIO(sample_csv))
    assert ingest_res["status"] == "PROCESSED"
    assert ingest_res["accepted_rows"] == 3

    # 3. Matching Funnel
    matching_svc = MatchingService(db_session, test_settings)
    metrics = matching_svc.execute_matching_funnel(import_id)

    assert metrics.users_evaluated == 3
    assert metrics.theoretical_pairs == 18
    assert metrics.pairs_after_sql_prefilter > 0
    assert metrics.deterministic_matches_found > 0

    # 4. Notification Dispatch
    notif_svc = NotificationService(db_session, test_settings)
    notif_summary = notif_svc.process_notifications_for_import(import_id)

    assert notif_summary.notifications_sent > 0
    assert notif_summary.delivery_mode == "test"

    # CRITICAL VERIFICATION:
    # Check that in notifications table, recipient is ONLY the safe test inbox
    notifications = db_session.query(Notification).filter(Notification.import_id == import_id).all()
    assert len(notifications) > 0
    for n in notifications:
        assert n.test_recipient == test_settings.TEST_EMAIL_RECIPIENTS
        assert "@originalsample.com" not in n.test_recipient
        assert n.status == "SENT"
        assert n.provider_message_id is not None

    # 5. Idempotency Check on duplicate notification trigger
    repeat_summary = notif_svc.process_notifications_for_import(import_id)
    # No new notifications should be dispatched
    assert repeat_summary.notifications_queued == 0
