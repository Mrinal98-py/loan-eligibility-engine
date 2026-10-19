from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from backend.app.models.base import Match, User, LoanProduct


class MatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def batch_insert_matches(self, matches_data: List[Dict[str, Any]], chunk_size: int = 1000) -> int:
        if not matches_data:
            return 0

        total_inserted = 0
        for i in range(0, len(matches_data), chunk_size):
            chunk = matches_data[i : i + chunk_size]
            stmt = insert(Match).values(chunk)
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_user_product_import"
            )
            result = self.db.execute(stmt)
            total_inserted += (result.rowcount or len(chunk))
        self.db.commit()
        return total_inserted

    def get_by_import_id(self, import_id: UUID) -> List[Match]:
        return (
            self.db.query(Match)
            .filter(Match.import_id == import_id)
            .order_by(Match.created_at)
            .all()
        )

    def get_distinct_matched_users(self, import_id: UUID) -> List[User]:
        return (
            self.db.query(User)
            .join(Match, Match.user_id == User.id)
            .filter(Match.import_id == import_id)
            .distinct()
            .all()
        )

    def get_user_matches(self, import_id: UUID, user_id: UUID) -> List[Match]:
        return (
            self.db.query(Match)
            .filter(Match.import_id == import_id, Match.user_id == user_id)
            .all()
        )
