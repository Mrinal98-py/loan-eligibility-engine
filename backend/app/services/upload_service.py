import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from backend.app.settings import Settings, get_settings
from backend.app.repositories.import_repo import ImportRepository
from backend.app.schemas.upload import UploadInitiateRequest, UploadInitiateResponse


class UploadService:
    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()
        self.import_repo = ImportRepository(db)

    def _get_s3_client(self):
        return boto3.client(
            "s3",
            region_name=self.settings.AWS_REGION,
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4")
        )

    def initiate_upload(self, req: UploadInitiateRequest, base_url: str = "") -> UploadInitiateResponse:
        # 1. Validation: size
        if req.size_bytes > self.settings.MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {req.size_bytes} exceeds maximum limit {self.settings.MAX_FILE_SIZE_BYTES} bytes")

        # 2. Validation: extension
        ext = os.path.splitext(req.filename)[1].lower()
        if ext not in self.settings.ALLOWED_EXTENSIONS:
            raise ValueError(f"File extension '{ext}' not supported. Allowed: {self.settings.ALLOWED_EXTENSIONS}")

        # 3. Generate secure non-user-controlled object key
        import_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        safe_filename = "".join(c for c in req.filename if c.isalnum() or c in "._-")
        object_key = f"uploads/{now.strftime('%Y/%m/%d')}/{import_id}/{safe_filename}"

        # 4. Generate presigned S3 URL or local upload URL
        if self.settings.ENVIRONMENT == "production" or (self.settings.AWS_ACCESS_KEY_ID and "mock" not in self.settings.AWS_ACCESS_KEY_ID):
            try:
                s3_client = self._get_s3_client()
                presigned_url = s3_client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={
                        "Bucket": self.settings.S3_BUCKET_NAME,
                        "Key": object_key,
                        "ContentType": req.content_type,
                        "ServerSideEncryption": "AES256",
                    },
                    ExpiresIn=self.settings.PRESIGNED_URL_EXPIRATION_SECONDS,
                )
            except ClientError as e:
                # Fallback for offline local dev mode
                presigned_url = f"{base_url}/api/uploads/local/{import_id}"
        else:
            # Local development mode: direct local upload endpoint
            presigned_url = f"{base_url}/api/uploads/local/{import_id}"

        # 5. Store import tracking record in database
        import_record = self.import_repo.create(
            original_filename=req.filename,
            object_key=object_key,
            file_size_bytes=req.size_bytes
        )

        return UploadInitiateResponse(
            import_id=import_record.id,
            object_key=object_key,
            upload_url=presigned_url,
            expires_in_seconds=self.settings.PRESIGNED_URL_EXPIRATION_SECONDS,
            instructions="PUT binary CSV data directly to upload_url with appropriate Content-Type header.",
            max_file_size_bytes=self.settings.MAX_FILE_SIZE_BYTES,
        )
