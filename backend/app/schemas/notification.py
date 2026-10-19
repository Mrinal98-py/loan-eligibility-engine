from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class NotificationWebhookRequest(BaseModel):
    import_id: UUID
    secret: Optional[str] = None


class NotificationResponse(BaseModel):
    id: UUID
    import_id: UUID
    user_id: UUID
    delivery_mode: str
    test_recipient: str
    status: str
    matched_products_count: int
    provider_message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime


class NotificationBatchSummary(BaseModel):
    import_id: UUID
    total_eligible_users: int
    notifications_queued: int
    notifications_sent: int
    notifications_failed: int
    delivery_mode: str
    test_recipients_used: List[str]
