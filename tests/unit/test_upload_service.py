import pytest
from backend.app.services.upload_service import UploadService
from backend.app.schemas.upload import UploadInitiateRequest


@pytest.mark.unit
def test_upload_service_rejects_non_csv(db_session, test_settings):
    svc = UploadService(db_session, test_settings)
    with pytest.raises(Exception):
        UploadInitiateRequest(
            filename="malicious.exe",
            content_type="application/octet-stream",
            size_bytes=1000
        )


@pytest.mark.unit
def test_upload_service_rejects_oversized_file(db_session, test_settings):
    svc = UploadService(db_session, test_settings)
    req = UploadInitiateRequest(
        filename="huge.csv",
        content_type="text/csv",
        size_bytes=200_000_000  # Exceeds 100 MB limit
    )
    with pytest.raises(ValueError, match="exceeds maximum limit"):
        svc.initiate_upload(req)


@pytest.mark.unit
def test_upload_service_generates_secure_key_and_record(db_session, test_settings, mock_aws_env):
    # Test local development mode
    svc = UploadService(db_session, test_settings)
    req = UploadInitiateRequest(
        filename="valid_users.csv",
        content_type="text/csv",
        size_bytes=5000
    )
    res = svc.initiate_upload(req, base_url="http://localhost:8000")
    assert res.import_id is not None
    assert "uploads/" in res.object_key
    assert "valid_users.csv" in res.object_key
    assert res.upload_url.startswith("http://localhost:8000/api/uploads/local/")

    # Test production AWS S3 presigned URL generation
    prod_settings = test_settings.model_copy(update={"ENVIRONMENT": "production", "AWS_ACCESS_KEY_ID": "prod_key"})
    prod_svc = UploadService(db_session, prod_settings)
    prod_res = prod_svc.initiate_upload(req)
    assert prod_res.upload_url.startswith("https://") or "amazonaws.com" in prod_res.upload_url
