import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime,
    ForeignKey, Text, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Import(Base):
    __tablename__ = "imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_key = Column(String(512), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="CREATED")
    file_hash = Column(String(64), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    total_rows = Column(Integer, default=0)
    accepted_rows = Column(Integer, default=0)
    rejected_rows = Column(Integer, default=0)
    error_summary = Column(JSONB, default=dict)
    matching_status = Column(String(50), default="PENDING")
    notification_status = Column(String(50), default="PENDING")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)

    users = relationship("User", back_populates="import_record", cascade="all, delete-orphan")
    rejected_records = relationship("RejectedRow", back_populates="import_record", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="import_record", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="import_record", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_user_id = Column(String(128), nullable=False)
    import_id = Column(UUID(as_uuid=True), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=False)
    monthly_income = Column(Numeric(14, 2), nullable=False)
    credit_score = Column(Integer, nullable=False)
    employment_status = Column(String(50), nullable=False)
    age = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    import_record = relationship("Import", back_populates="users")
    matches = relationship("Match", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("import_id", "external_user_id", name="uq_import_external_user"),
        Index("idx_users_import_id", "import_id"),
        Index("idx_users_matching_composite", "import_id", "monthly_income", "credit_score", "age", "employment_status"),
    )


class RejectedRow(Base):
    __tablename__ = "rejected_rows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id = Column(UUID(as_uuid=True), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)
    external_user_id = Column(String(128), nullable=True)
    rejection_reason = Column(String(500), nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    import_record = relationship("Import", back_populates="rejected_records")


class LoanProduct(Base):
    __tablename__ = "loan_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name = Column(String(128), nullable=False)
    source_url = Column(String(512), nullable=False)
    product_name = Column(String(255), nullable=False)
    product_type = Column(String(100), nullable=False, default="Personal Loan")
    interest_rate_min = Column(Numeric(5, 2), nullable=True)
    interest_rate_max = Column(Numeric(5, 2), nullable=True)
    min_monthly_income = Column(Numeric(14, 2), default=0.0)
    min_credit_score = Column(Integer, default=300)
    max_credit_score = Column(Integer, nullable=True)
    min_age = Column(Integer, default=18)
    max_age = Column(Integer, default=100)
    eligible_employment_statuses = Column(JSONB, default=lambda: ["Salaried", "Self-Employed", "Business"])
    eligibility_criteria_raw = Column(Text, nullable=True)
    eligibility_evidence = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    scraped_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    matches = relationship("Match", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source_url", "product_name", name="uq_source_product"),
        Index("idx_products_active", "is_active"),
        Index("idx_products_matching", "is_active", "min_monthly_income", "min_credit_score", "min_age", "max_age"),
    )


class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("loan_products.id", ondelete="CASCADE"), nullable=False)
    import_id = Column(UUID(as_uuid=True), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False)
    rule_version = Column(String(32), default="v1.0", nullable=False)
    match_score = Column(Numeric(5, 2), default=100.0)
    match_reasons = Column(JSONB, default=list, nullable=False)
    status = Column(String(50), default="CONFIRMED", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="matches")
    product = relationship("LoanProduct", back_populates="matches")
    import_record = relationship("Import", back_populates="matches")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "import_id", name="uq_user_product_import"),
        Index("idx_matches_import_id", "import_id"),
        Index("idx_matches_user_id", "user_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id = Column(UUID(as_uuid=True), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delivery_mode = Column(String(20), default="test", nullable=False)
    test_recipient = Column(String(255), nullable=False)
    status = Column(String(50), default="QUEUED", nullable=False)
    provider_message_id = Column(String(255), nullable=True)
    matched_products_count = Column(Integer, default=1, nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    import_record = relationship("Import", back_populates="notifications")
    user = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("idx_notifications_import_status", "import_id", "status"),
    )


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name = Column(String(128), nullable=False)
    source_url = Column(String(512), nullable=False)
    status = Column(String(50), nullable=False)
    products_found = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    response_status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    executed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
