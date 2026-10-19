#!/usr/bin/env python3
"""
One-command End-to-End Local Demonstration of the Loan Eligibility Engine.
Executes CSV ingestion, SQL pre-filtering, rule evaluation, and test notification dispatch.
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal, engine
from backend.app.models.base import Import, User, LoanProduct, Match, Notification
from backend.app.services.upload_service import UploadService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.matching_service import MatchingService
from backend.app.services.notification_service import NotificationService
from backend.app.schemas.upload import UploadInitiateRequest
from scripts.seed_demo_products import seed
from scripts.benchmark_matching import run_benchmark


def run_demo():
    print("\n" + "=" * 80)
    print("  LOAN ELIGIBILITY ENGINE - END-TO-END DEMO EXECUTION")
    print("=" * 80)

    db = SessionLocal()
    try:
        # Step 1: Ensure products seeded
        print("\n[Step 1/6] Checking verified loan products database...")
        seed()
        active_prods = db.query(LoanProduct).filter(LoanProduct.is_active.is_(True)).count()
        print(f"  ✓ {active_prods} active loan products available in registry.")

        # Step 2: Locate sample CSV
        fixture_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n8n", "fixtures", "sample_users_10k.csv")
        if not os.path.exists(fixture_path):
            fixture_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n8n", "fixtures", "sample_users_small.csv")

        file_size = os.path.getsize(fixture_path)
        print(f"\n[Step 2/6] Initiating upload for sample CSV ({os.path.basename(fixture_path)}, {file_size:,} bytes)...")
        upload_svc = UploadService(db)
        upload_res = upload_svc.initiate_upload(UploadInitiateRequest(
            filename=os.path.basename(fixture_path),
            content_type="text/csv",
            size_bytes=file_size,
        ))
        import_id = upload_res.import_id
        print(f"  ✓ Generated Import ID: {import_id}")
        print(f"  ✓ Presigned/Direct Upload Endpoint: {upload_res.upload_url}")

        # Step 3: Stream Ingestion
        print(f"\n[Step 3/6] Streaming CSV into Ingestion Service with row-level validation...")
        ingestion_svc = IngestionService(db)
        with open(fixture_path, "r", encoding="utf-8") as f:
            ingest_result = ingestion_svc.process_csv_stream(import_id, f)

        print(f"  ✓ Ingestion Status: {ingest_result['status']}")
        print(f"  ✓ Total Rows Processed : {ingest_result['total_rows']:,}")
        print(f"  ✓ Accepted User Records: {ingest_result['accepted_rows']:,}")
        print(f"  ✓ Rejected Rows Count  : {ingest_result['rejected_rows']:,}")
        print(f"  ✓ Computed File Hash   : {ingest_result['file_hash'][:16]}...")

        # Step 4: Optimized Matching Funnel
        print(f"\n[Step 4/6] Executing Workflow B: Optimized SQL Pre-Filter & Eligibility Engine...")
        matching_svc = MatchingService(db)
        metrics = matching_svc.execute_matching_funnel(import_id)

        print(f"  ✓ Theoretical Candidate Pairs (N × M) : {metrics.theoretical_pairs:,}")
        print(f"  ✓ Surviving SQL Hard-Rule Predicates   : {metrics.pairs_after_sql_prefilter:,}")
        print(f"  ✓ Candidate Reduction Ratio            : {metrics.sql_reduction_percentage:.2f}%")
        print(f"  ✓ Confirmed Matches Idempotently Stored : {metrics.deterministic_matches_found:,}")
        print(f"  ✓ Matching Execution Time              : {metrics.duration_ms} ms")

        # Step 5: Safe Notification Dispatch
        print(f"\n[Step 5/6] Executing Workflow C: Safe Notifications via Amazon SES...")
        notif_svc = NotificationService(db)
        notif_summary = notif_svc.process_notifications_for_import(import_id, max_dispatch=50)

        print(f"  ✓ Delivery Mode           : {notif_summary.delivery_mode.upper()} (Zero sample emails contacted)")
        print(f"  ✓ Eligible Users Found    : {notif_summary.total_eligible_users:,}")
        print(f"  ✓ Controlled Test Inboxes : {notif_summary.test_recipients_used}")
        print(f"  ✓ Notifications Dispatched: {notif_summary.notifications_sent:,}")

        # Step 6: Benchmark Treasure Hunt
        print(f"\n[Step 6/6] Generating Treasure Hunt Optimization Report...")
        run_benchmark(str(import_id))

        print("\n" + "=" * 80)
        print("  END-TO-END DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 80 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    run_demo()
