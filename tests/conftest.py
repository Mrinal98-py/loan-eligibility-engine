import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moto import mock_aws
import boto3

from backend.app.database import Base
from backend.app.settings import Settings
from backend.app.models.base import LoanProduct
from scripts.seed_demo_products import PRODUCTS

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://mrinal@localhost:5432/loan_engine_test")


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    # Seed verified loan products in test database
    for p in PRODUCTS:
        from backend.app.repositories.product_repo import LoanProductRepository
        repo = LoanProductRepository(session)
        repo.upsert_product(p)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_settings():
    return Settings(
        ENVIRONMENT="test",
        DATABASE_URL=TEST_DB_URL,
        DELIVERY_MODE="test",
        ALLOW_REAL_RECIPIENTS=False,
        TEST_EMAIL_RECIPIENTS="developer-test-inbox@example.com",
        WEBHOOK_SECRET="test-secret-token",
        S3_BUCKET_NAME="test-loan-uploads",
        AWS_REGION="us-east-1",
        AWS_ACCESS_KEY_ID="mock_access_key",
        AWS_SECRET_ACCESS_KEY="mock_secret_key",
    )


@pytest.fixture
def mock_aws_env(test_settings):
    with mock_aws():
        s3 = boto3.client("s3", region_name=test_settings.AWS_REGION)
        s3.create_bucket(Bucket=test_settings.S3_BUCKET_NAME)

        sqs = boto3.client("sqs", region_name=test_settings.AWS_REGION)
        dlq_res = sqs.create_queue(QueueName="test-dlq")
        q_res = sqs.create_queue(QueueName="test-queue")

        ses = boto3.client("ses", region_name=test_settings.AWS_REGION)
        ses.verify_email_identity(EmailAddress=test_settings.SES_FROM_EMAIL)

        yield {
            "s3": s3,
            "sqs": sqs,
            "ses": ses,
            "queue_url": q_res["QueueUrl"],
            "dlq_url": dlq_res["QueueUrl"],
        }
