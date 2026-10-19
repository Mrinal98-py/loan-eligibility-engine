import io
import pytest
from backend.app.services.upload_service import UploadService
from backend.app.services.ingestion_service import IngestionService
from backend.app.schemas.upload import UploadInitiateRequest
from backend.app.models.base import User, RejectedRow, Import


@pytest.mark.integration
def test_streaming_ingestion_with_mixed_rows(db_session, test_settings):
    upload_svc = UploadService(db_session, test_settings)
    req = UploadInitiateRequest(filename="mixed.csv", content_type="text/csv", size_bytes=2000)
    upload_res = upload_svc.initiate_upload(req)
    import_id = upload_res.import_id

    csv_data = """user_id,name,email,monthly_income,credit_score,employment_status,age
u-valid-1,Rohit Sharma,rohit@example.com,65000,750,Salaried,34
u-bad-income,Bad Income,bad.inc@example.com,-10000,750,Salaried,30
u-valid-2,Priya Nair,priya@example.com,85000,780,Self-Employed,36
u-bad-credit,Bad Score,bad.score@example.com,50000,200,Salaried,28
u-dup,Dup First,dup1@example.com,40000,700,Salaried,25
u-dup,Dup Second,dup2@example.com,40000,700,Salaried,25
"""

    ingestion_svc = IngestionService(db_session, test_settings)
    stream = io.StringIO(csv_data)
    result = ingestion_svc.process_csv_stream(import_id, stream)

    assert result["status"] == "PARTIAL_REJECTED"
    assert result["total_rows"] == 6
    assert result["accepted_rows"] == 3  # u-valid-1, u-valid-2, u-dup (first)
    assert result["rejected_rows"] == 3  # u-bad-income, u-bad-credit, u-dup (second)

    # Verify persistence
    users_in_db = db_session.query(User).filter(User.import_id == import_id).count()
    assert users_in_db == 3

    rejected_in_db = db_session.query(RejectedRow).filter(RejectedRow.import_id == import_id).count()
    assert rejected_in_db == 3

    import_rec = db_session.query(Import).filter(Import.id == import_id).first()
    assert import_rec.status == "PARTIAL_REJECTED"
    assert import_rec.file_hash is not None
