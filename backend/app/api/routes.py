import io
from typing import List, Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File, Request, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.settings import Settings, get_settings
from backend.app.schemas.upload import (
    UploadInitiateRequest,
    UploadInitiateResponse,
    ImportStatusResponse,
    RejectedRowResponse,
)
from backend.app.schemas.product import LoanProductResponse
from backend.app.schemas.match import MatchingWebhookRequest, MatchResponse, MatchingFunnelMetrics
from backend.app.schemas.notification import NotificationWebhookRequest, NotificationResponse, NotificationBatchSummary
from backend.app.services.upload_service import UploadService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.discovery_service import DiscoveryService
from backend.app.services.matching_service import MatchingService
from backend.app.services.notification_service import NotificationService
from backend.app.models.base import LoanProduct, Match, Notification, RejectedRow

router = APIRouter(prefix="/api", tags=["Loan Engine"])


@router.get("/health")
def health_check(settings: Settings = Depends(get_settings)):
    return {
        "status": "healthy",
        "service": "loan-eligibility-engine",
        "environment": settings.ENVIRONMENT,
        "delivery_mode": settings.DELIVERY_MODE,
    }


@router.post("/uploads", response_model=UploadInitiateResponse)
def initiate_upload(
    req: UploadInitiateRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    service = UploadService(db, settings)
    base_url = str(request.base_url).rstrip("/")
    try:
        return service.initiate_upload(req, base_url=base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/uploads/local/{import_id}")
@router.post("/uploads/local/{import_id}")
async def upload_local_file(
    import_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """Local development direct upload adapter. Streams CSV and triggers processing immediately."""
    ingestion = IngestionService(db, settings)
    content = await file.read()
    stream = io.StringIO(content.decode("utf-8", errors="replace"))

    result = ingestion.process_csv_stream(import_id, stream)

    # In local mode, immediately trigger matching funnel and notifications
    matching_svc = MatchingService(db, settings)
    funnel_metrics = matching_svc.execute_matching_funnel(import_id)

    notification_svc = NotificationService(db, settings)
    notif_summary = notification_svc.process_notifications_for_import(import_id)

    return {
        "ingestion": result,
        "funnel_metrics": funnel_metrics,
        "notification_summary": notif_summary,
    }


@router.get("/imports/{import_id}", response_model=ImportStatusResponse)
def get_import_status(import_id: UUID, db: Session = Depends(get_db)):
    from backend.app.repositories.import_repo import ImportRepository
    repo = ImportRepository(db)
    record = repo.get_by_id(import_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Import {import_id} not found")

    return ImportStatusResponse(
        import_id=record.id,
        original_filename=record.original_filename,
        status=record.status,
        file_hash=record.file_hash,
        file_size_bytes=record.file_size_bytes,
        total_rows=record.total_rows,
        accepted_rows=record.accepted_rows,
        rejected_rows=record.rejected_rows,
        error_summary=record.error_summary or {},
        matching_status=record.matching_status,
        notification_status=record.notification_status,
        created_at=record.created_at,
        uploaded_at=record.uploaded_at,
        processing_started_at=record.processing_started_at,
        processing_completed_at=record.processing_completed_at,
    )


@router.get("/imports/{import_id}/rejected", response_model=List[RejectedRowResponse])
def get_rejected_rows(import_id: UUID, db: Session = Depends(get_db)):
    rows = db.query(RejectedRow).filter(RejectedRow.import_id == import_id).order_by(RejectedRow.row_number).all()
    return [
        RejectedRowResponse(
            row_number=r.row_number,
            external_user_id=r.external_user_id,
            rejection_reason=r.rejection_reason,
            raw_payload=r.raw_payload,
        )
        for r in rows
    ]


@router.post("/matching/webhook", response_model=MatchingFunnelMetrics)
def trigger_matching_webhook(
    req: MatchingWebhookRequest,
    x_webhook_secret: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Protected webhook for n8n Workflow B to trigger candidate matching."""
    provided_secret = x_webhook_secret or req.secret
    if provided_secret != settings.WEBHOOK_SECRET and settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=401, detail="Unauthorized webhook secret")

    service = MatchingService(db, settings)
    return service.execute_matching_funnel(req.import_id)


@router.post("/notifications/webhook", response_model=NotificationBatchSummary)
def trigger_notifications_webhook(
    req: NotificationWebhookRequest,
    x_webhook_secret: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Protected webhook for n8n Workflow C to dispatch safe notifications."""
    provided_secret = x_webhook_secret or req.secret
    if provided_secret != settings.WEBHOOK_SECRET and settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=401, detail="Unauthorized webhook secret")

    service = NotificationService(db, settings)
    return service.process_notifications_for_import(req.import_id)


@router.get("/products", response_model=List[LoanProductResponse])
def list_products(db: Session = Depends(get_db)):
    products = db.query(LoanProduct).filter(LoanProduct.is_active.is_(True)).all()
    return [
        LoanProductResponse(
            id=p.id,
            source_name=p.source_name,
            source_url=p.source_url,
            product_name=p.product_name,
            product_type=p.product_type,
            interest_rate_min=p.interest_rate_min,
            interest_rate_max=p.interest_rate_max,
            min_monthly_income=p.min_monthly_income,
            min_credit_score=p.min_credit_score,
            max_credit_score=p.max_credit_score,
            min_age=p.min_age,
            max_age=p.max_age,
            eligible_employment_statuses=p.eligible_employment_statuses or [],
            eligibility_evidence=p.eligibility_evidence or {},
            is_active=p.is_active,
            scraped_at=p.scraped_at,
        )
        for p in products
    ]


@router.post("/products/discover")
def trigger_product_discovery(
    fixture_path: Optional[str] = "n8n/fixtures/mock_bank_offers.html",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """Triggers product discovery crawl (supports local fixture or live endpoints)."""
    service = DiscoveryService(db, settings)
    html_content = None
    if fixture_path:
        with open(fixture_path, "r", encoding="utf-8") as f:
            html_content = f.read()

    discovered = service.discover_and_upsert(
        source_name="Financial Portals Registry",
        source_url="https://bank-offers.internal/personal-loans",
        html_content=html_content
    )
    return {"status": "SUCCESS", "products_discovered_count": len(discovered)}


@router.get("/matches/{import_id}", response_model=List[MatchResponse])
def get_matches(import_id: UUID, db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .join(LoanProduct, LoanProduct.id == Match.product_id)
        .filter(Match.import_id == import_id)
        .all()
    )
    return [
        MatchResponse(
            id=m.id,
            user_id=m.user_id,
            product_id=m.product_id,
            product_name=m.product.product_name,
            source_name=m.product.source_name,
            interest_rate_min=m.product.interest_rate_min,
            interest_rate_max=m.product.interest_rate_max,
            match_score=m.match_score,
            match_reasons=m.match_reasons,
            status=m.status,
            created_at=m.created_at,
        )
        for m in matches
    ]


@router.get("/notifications/{import_id}", response_model=List[NotificationResponse])
def get_notifications(import_id: UUID, db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(Notification.import_id == import_id).all()
    return [
        NotificationResponse(
            id=n.id,
            import_id=n.import_id,
            user_id=n.user_id,
            delivery_mode=n.delivery_mode,
            test_recipient=n.test_recipient,
            status=n.status,
            matched_products_count=n.matched_products_count,
            provider_message_id=n.provider_message_id,
            sent_at=n.sent_at,
            created_at=n.created_at,
        )
        for n in notifs
    ]
