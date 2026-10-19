from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.base import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def batch_insert(self, users_data: List[Dict[str, Any]]) -> int:
        if not users_data:
            return 0
        objects = [User(**item) for item in users_data]
        self.db.bulk_save_objects(objects)
        self.db.commit()
        return len(objects)

    def get_by_import_id(self, import_id: UUID, limit: Optional[int] = None, offset: int = 0) -> List[User]:
        query = self.db.query(User).filter(User.import_id == import_id).order_by(User.created_at)
        if offset > 0:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count_by_import_id(self, import_id: UUID) -> int:
        return self.db.query(func.count(User.id)).filter(User.import_id == import_id).scalar() or 0
