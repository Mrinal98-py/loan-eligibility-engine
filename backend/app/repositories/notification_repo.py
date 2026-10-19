from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from backend.app.models.base import Notification


def utcnow():
    return datetime.now(timezone.utc)


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        import_id: UUID,
        user_id: UUID,
        delivery_mode: str,
        test_recipient: str,
        matched_products_count: int,
        status: str = "QUEUED",
        provider_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Notification:
        record = Notification(
            import_id=import_id,
            user_id=user_id,
            delivery_mode=delivery_mode,
            test_recipient=test_recipient,
            matched_products_count=matched_products_count,
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
            sent_at=utcnow() if status == "SENT" else None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_import_id(self, import_id: UUID) -> List[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.import_id == import_id)
            .order_by(Notification.created_at)
            .all()
        )

    def mark_sent(self, notification_id: UUID, provider_message_id: str) -> Optional[Notification]:
        record = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if record:
            record.status = "SENT"
            record.provider_message_id = provider_message_id
            record.sent_at = utcnow()
            record.attempt_count += 1
            self.db.commit()
            self.db.refresh(record)
        return record

    def mark_failed(self, notification_id: UUID, error_message: str) -> Optional[Notification]:
        record = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if record:
            record.status = "FAILED"
            record.error_message = error_message
            record.attempt_count += 1
            self.db.commit()
            self.db.refresh(record)
        return record
