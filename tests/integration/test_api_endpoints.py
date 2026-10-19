import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db
from backend.app.settings import get_settings


@pytest.fixture
def client(db_session, test_settings):
    def override_get_db():
        yield db_session

    def override_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.integration
def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


@pytest.mark.integration
def test_products_list_endpoint(client):
    res = client.get("/api/products")
    assert res.status_code == 200
    products = res.json()
    assert len(products) >= 6
    assert any(p["product_name"] == "HDFC Bank Personal Loan for Salaried" for p in products)


@pytest.mark.integration
def test_upload_initiate_endpoint(client):
    payload = {
        "filename": "applicant_batch.csv",
        "content_type": "text/csv",
        "size_bytes": 1024,
    }
    res = client.post("/api/uploads", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "import_id" in data
    assert "upload_url" in data
