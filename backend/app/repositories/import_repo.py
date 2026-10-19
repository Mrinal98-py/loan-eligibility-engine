from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from backend.app.models.base import Import, RejectedRow


def utcnow():
    return datetime.now(timezone.utc)


class ImportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, original_filename: str, object_key: str, file_size_bytes: Optional[int] = None) -> Import:
        import_record = Import(
            original_filename=original_filename,
            object_key=object_key,
            file_size_bytes=file_size_bytes,
            status="CREATED",
        )
        self.db.add(import_record)
        self.db.commit()
        self.db.refresh(import_record)
        return import_record

    def get_by_id(self, import_id: UUID) -> Optional[Import]:
        return self.db.query(Import).filter(Import.id == import_id).first()

    def get_by_object_key(self, object_key: str) -> Optional[Import]:
        return self.db.query(Import).filter(Import.object_key == object_key).first()

    def mark_uploaded(self, import_id: UUID) -> Optional[Import]:
        record = self.get_by_id(import_id)
        if record:
            record.status = "UPLOADED"
            record.uploaded_at = utcnow()
            self.db.commit()
            self.db.refresh(record)
        return record

    def mark_processing_started(self, import_id: UUID, file_hash: Optional[str] = None) -> Optional[Import]:
        record = self.get_by_id(import_id)
        if record:
            record.status = "PROCESSING"
            record.processing_started_at = utcnow()
            if file_hash:
                record.file_hash = file_hash
            self.db.commit()
            self.db.refresh(record)
        return record

    def update_completion(
        self,
        import_id: UUID,
        status: str,
        total_rows: int,
        accepted_rows: int,
        rejected_rows: int,
        error_summary: Optional[Dict[str, Any]] = None,
        file_hash: Optional[str] = None,
    ) -> Optional[Import]:
        record = self.get_by_id(import_id)
        if record:
            record.status = status
            record.total_rows = total_rows
            record.accepted_rows = accepted_rows
            record.rejected_rows = rejected_rows
            if error_summary:
                record.error_summary = error_summary
            if file_hash:
                record.file_hash = file_hash
            record.processing_completed_at = utcnow()
            self.db.commit()
            self.db.refresh(record)
        return record

    def update_matching_status(self, import_id: UUID, status: str) -> Optional[Import]:
        record = self.get_by_id(import_id)
        if record:
            record.matching_status = status
            self.db.commit()
            self.db.refresh(record)
        return record

    def update_notification_status(self, import_id: UUID, status: str) -> Optional[Import]:
        record = self.get_by_id(import_id)
        if record:
            record.notification_status = status
            self.db.commit()
            self.db.refresh(record)
        return record

    def add_rejected_rows_batch(self, rejected_records: list[dict]) -> None:
        if not rejected_records:
            return
        objects = [RejectedRow(**row) for row in rejected_records]
        self.db.bulk_save_objects(objects)
        self.db.commit()
