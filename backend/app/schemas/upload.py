from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class UploadInitiateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255, description="Original filename including .csv")
    content_type: str = Field(..., description="Declared MIME type")
    size_bytes: int = Field(..., gt=0, description="File size in bytes")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        clean_name = v.strip().lower()
        if not clean_name.endswith(".csv"):
            raise ValueError("Only .csv files are supported")
        return v.strip()


class UploadInitiateResponse(BaseModel):
    import_id: UUID
    object_key: str
    upload_url: str
    expires_in_seconds: int
    instructions: str
    max_file_size_bytes: int


class ImportStatusResponse(BaseModel):
    import_id: UUID
    original_filename: str
    status: str
    file_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    error_summary: Dict[str, Any]
    matching_status: str
    notification_status: str
    created_at: datetime
    uploaded_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None


class RejectedRowResponse(BaseModel):
    row_number: int
    external_user_id: Optional[str]
    rejection_reason: str
    raw_payload: Dict[str, Any]
