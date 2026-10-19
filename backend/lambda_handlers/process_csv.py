import json
from uuid import UUID
import boto3
from backend.app.database import SessionLocal
from backend.app.settings import get_settings
from backend.app.repositories.import_repo import ImportRepository
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.matching_service import MatchingService


def handler(event, context):
    """
    AWS Lambda Handler triggered by Amazon SQS.
    Streams CSV directly from S3, parses rows, runs batch DB ingestion,
    and initiates the matching workflow upon persistence.
    """
    settings = get_settings()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    db = SessionLocal()
    ingestion_service = IngestionService(db, settings)
    import_repo = ImportRepository(db)

    processed_imports = []

    try:
        for record in event.get("Records", []):
            body = json.loads(record.get("body", "{}"))
            bucket = body.get("bucket_name")
            key = body.get("object_key")

            if not bucket or not key:
                continue

            import_record = import_repo.get_by_object_key(key)
            if not import_record:
                # Key format: uploads/YYYY/MM/DD/{import_id}/{filename}
                parts = key.split("/")
                if len(parts) >= 5:
                    try:
                        import_id = UUID(parts[4])
                        import_record = import_repo.get_by_id(import_id)
                    except ValueError:
                        pass

            if not import_record:
                print(f"[Ingestion Worker] No import record found for key: {key}")
                continue

            # Stream object lines directly from S3
            response = s3.get_object(Bucket=bucket, Key=key)
            lines_stream = (line.decode("utf-8", errors="replace") for line in response["Body"].iter_lines())

            result = ingestion_service.process_csv_stream(import_record.id, lines_stream)
            processed_imports.append(result)

            # Once persisted, trigger matching pipeline
            if result.get("status") in ("PROCESSED", "PARTIAL_REJECTED"):
                ingestion_service.trigger_matching_workflow(import_record.id)

        return {
            "statusCode": 200,
            "processed_count": len(processed_imports),
            "results": processed_imports,
        }
    finally:
        db.close()
