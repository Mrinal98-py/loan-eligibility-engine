import json
from uuid import UUID
from backend.app.database import SessionLocal
from backend.app.settings import get_settings
from backend.app.services.upload_service import UploadService
from backend.app.schemas.upload import UploadInitiateRequest


def handler(event, context):
    """
    AWS Lambda Handler for POST /api/uploads via API Gateway.
    Generates S3 presigned URL for direct client upload.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        req = UploadInitiateRequest(**body)
    except Exception as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": f"Invalid request payload: {str(e)}"}),
        }

    db = SessionLocal()
    try:
        settings = get_settings()
        service = UploadService(db, settings)
        result = service.initiate_upload(req)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "import_id": str(result.import_id),
                "object_key": result.object_key,
                "upload_url": result.upload_url,
                "expires_in_seconds": result.expires_in_seconds,
                "instructions": result.instructions,
                "max_file_size_bytes": result.max_file_size_bytes,
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": f"Internal server error: {str(e)}"}),
        }
    finally:
        db.close()
