from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from backend.app.models.base import LoanProduct, ExtractionRun


def utcnow():
    return datetime.now(timezone.utc)


class LoanProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_active(self) -> List[LoanProduct]:
        return self.db.query(LoanProduct).filter(LoanProduct.is_active.is_(True)).all()

    def get_by_id(self, product_id: UUID) -> Optional[LoanProduct]:
        return self.db.query(LoanProduct).filter(LoanProduct.id == product_id).first()

    def upsert_product(self, product_dict: Dict[str, Any]) -> LoanProduct:
        stmt = insert(LoanProduct).values(**product_dict)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in LoanProduct.__table__.columns
            if col.name not in ("id", "created_at")
        }
        update_cols["updated_at"] = utcnow()

        stmt = stmt.on_conflict_do_update(
            constraint="uq_source_product",
            set_=update_cols
        )
        self.db.execute(stmt)
        self.db.commit()

        return self.db.query(LoanProduct).filter(
            LoanProduct.source_url == product_dict["source_url"],
            LoanProduct.product_name == product_dict["product_name"]
        ).first()

    def record_extraction_run(
        self,
        source_name: str,
        source_url: str,
        status: str,
        products_found: int,
        error_message: Optional[str] = None,
        response_status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> ExtractionRun:
        run = ExtractionRun(
            source_name=source_name,
            source_url=source_url,
            status=status,
            products_found=products_found,
            error_message=error_message,
            response_status_code=response_status_code,
            duration_ms=duration_ms,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
