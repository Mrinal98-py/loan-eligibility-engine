import json
from uuid import UUID
from backend.app.database import SessionLocal
from backend.app.repositories.import_repo import ImportRepository


def handler(event, context):
    """
    AWS Lambda Handler for GET /api/imports/{import_id}.
    Returns live ingestion and workflow processing status.
    """
    path_params = event.get("pathParameters", {}) or {}
    import_id_str = path_params.get("import_id")

    if not import_id_str:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Missing import_id path parameter"}),
        }

    try:
        import_id = UUID(import_id_str)
    except ValueError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Invalid UUID format for import_id"}),
        }

    db = SessionLocal()
    try:
        repo = ImportRepository(db)
        record = repo.get_by_id(import_id)

        if not record:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": f"Import {import_id} not found"}),
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "import_id": str(record.id),
                "original_filename": record.original_filename,
                "status": record.status,
                "file_hash": record.file_hash,
                "file_size_bytes": record.file_size_bytes,
                "total_rows": record.total_rows,
                "accepted_rows": record.accepted_rows,
                "rejected_rows": record.rejected_rows,
                "error_summary": record.error_summary or {},
                "matching_status": record.matching_status,
                "notification_status": record.notification_status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "processing_started_at": record.processing_started_at.isoformat() if record.processing_started_at else None,
                "processing_completed_at": record.processing_completed_at.isoformat() if record.processing_completed_at else None,
            }),
        }
    finally:
        db.close()
