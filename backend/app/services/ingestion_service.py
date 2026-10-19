import csv
import hashlib
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Tuple, Iterator
from uuid import UUID
import httpx
from sqlalchemy.orm import Session
from backend.app.settings import Settings, get_settings
from backend.app.repositories.import_repo import ImportRepository
from backend.app.repositories.user_repo import UserRepository

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
VALID_EMPLOYMENT = {"salaried": "Salaried", "self-employed": "Self-Employed", "business": "Business", "other": "Other"}
BATCH_SIZE = 1000


class IngestionService:
    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()
        self.import_repo = ImportRepository(db)
        self.user_repo = UserRepository(db)

    def _sanitize_formula(self, value: str) -> str:
        """Prevent spreadsheet formula injection."""
        if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + value
        return value

    def validate_row(
        self,
        row: Dict[str, str],
        row_number: int,
        seen_user_ids: set
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Validates single CSV row. Returns (validated_dict, None) or (None, rejection_reason)."""
        # 1. Blank row check
        if not any(v.strip() for v in row.values() if v):
            return None, "Empty row"

        raw_user_id = row.get("user_id", "").strip()
        if not raw_user_id:
            return None, "Missing required column: user_id"

        if raw_user_id in seen_user_ids:
            return None, f"Duplicate user_id '{raw_user_id}' within file"

        # 2. Email check
        raw_email = row.get("email", "").strip()
        if not raw_email or not EMAIL_REGEX.match(raw_email):
            return None, f"Invalid email format: '{raw_email}'"

        # 3. Monthly Income check
        raw_income = row.get("monthly_income", "").strip()
        try:
            income = Decimal(raw_income)
            if income < 0:
                return None, f"Negative monthly income: {raw_income}"
            if income > Decimal("1000000000"):
                return None, f"Monthly income out of realistic domain: {raw_income}"
        except (InvalidOperation, ValueError):
            return None, f"Invalid numeric monthly_income: '{raw_income}'"

        # 4. Credit Score check
        raw_credit = row.get("credit_score", "").strip()
        try:
            credit_score = int(raw_credit)
            if credit_score < 300 or credit_score > 900:
                return None, f"Credit score {credit_score} outside supported range (300-900)"
        except ValueError:
            return None, f"Invalid integer credit_score: '{raw_credit}'"

        # 5. Age check
        raw_age = row.get("age", "").strip()
        try:
            age = int(raw_age)
            if age < 18 or age > 120:
                return None, f"Age {age} outside legal/supported range (18-120)"
        except ValueError:
            return None, f"Invalid integer age: '{raw_age}'"

        # 6. Employment Status check
        raw_emp = row.get("employment_status", "").strip().lower()
        if raw_emp not in VALID_EMPLOYMENT:
            return None, f"Invalid employment_status '{row.get('employment_status')}'. Allowed: Salaried, Self-Employed, Business, Other"
        normalized_emp = VALID_EMPLOYMENT[raw_emp]

        seen_user_ids.add(raw_user_id)
        name = row.get("name", "").strip() if row.get("name") else None

        return {
            "external_user_id": raw_user_id,
            "name": self._sanitize_formula(name) if name else None,
            "email": raw_email.lower(),
            "monthly_income": income,
            "credit_score": credit_score,
            "employment_status": normalized_emp,
            "age": age,
        }, None

    def process_csv_stream(self, import_id: UUID, stream: Iterator[str]) -> Dict[str, Any]:
        """
        Memory-efficient streaming ingestion of CSV lines.
        Computes SHA256 on the fly, validates row by row, and writes in chunks.
        """
        import_record = self.import_repo.get_by_id(import_id)
        if not import_record:
            raise ValueError(f"Import record {import_id} not found")

        # Check idempotency: if already processed, do not duplicate
        if import_record.status == "PROCESSED":
            return {
                "import_id": str(import_id),
                "status": "PROCESSED",
                "message": "Already processed (idempotent skip)",
                "total_rows": import_record.total_rows,
                "accepted_rows": import_record.accepted_rows,
                "rejected_rows": import_record.rejected_rows,
            }

        hasher = hashlib.sha256()
        reader = csv.reader(stream)

        try:
            headers = next(reader)
        except StopIteration:
            self.import_repo.update_completion(
                import_id, status="FAILED", total_rows=0, accepted_rows=0, rejected_rows=0,
                error_summary={"error": "Empty file"}
            )
            return {"status": "FAILED", "error": "Empty file"}

        cleaned_headers = [h.strip().lower() for h in headers]
        required_headers = {"user_id", "email", "monthly_income", "credit_score", "employment_status", "age"}
        missing = required_headers - set(cleaned_headers)
        if missing:
            err = f"Missing required CSV columns: {sorted(list(missing))}"
            self.import_repo.update_completion(
                import_id, status="FAILED", total_rows=0, accepted_rows=0, rejected_rows=0,
                error_summary={"error": err}
            )
            return {"status": "FAILED", "error": err}

        # Update status to PROCESSING
        self.import_repo.mark_processing_started(import_id)

        header_index = {name: i for i, name in enumerate(cleaned_headers)}
        total_rows = 0
        accepted_rows = 0
        rejected_rows = 0
        seen_user_ids = set()

        user_batch = []
        rejected_batch = []
        error_reasons_counter = {}

        for row in reader:
            total_rows += 1
            hasher.update(",".join(row).encode("utf-8"))

            row_dict = {}
            for h, idx in header_index.items():
                row_dict[h] = row[idx] if idx < len(row) else ""

            validated, reason = self.validate_row(row_dict, total_rows, seen_user_ids)
            if validated:
                validated["import_id"] = import_id
                user_batch.append(validated)
                accepted_rows += 1
            else:
                rejected_rows += 1
                error_reasons_counter[reason] = error_reasons_counter.get(reason, 0) + 1
                rejected_batch.append({
                    "import_id": import_id,
                    "row_number": total_rows,
                    "external_user_id": row_dict.get("user_id"),
                    "rejection_reason": reason,
                    "raw_payload": row_dict,
                })

            # Flush batch
            if len(user_batch) >= BATCH_SIZE:
                self.user_repo.batch_insert(user_batch)
                user_batch.clear()

            if len(rejected_batch) >= BATCH_SIZE:
                self.import_repo.add_rejected_rows_batch(rejected_batch)
                rejected_batch.clear()

        # Flush remaining
        if user_batch:
            self.user_repo.batch_insert(user_batch)
            user_batch.clear()
        if rejected_batch:
            self.import_repo.add_rejected_rows_batch(rejected_batch)
            rejected_batch.clear()

        final_status = "PROCESSED"
        if accepted_rows == 0 and total_rows > 0:
            final_status = "FAILED"
        elif rejected_rows > 0:
            final_status = "PARTIAL_REJECTED"

        file_hash = hasher.hexdigest()
        summary = {
            "rejection_breakdown": error_reasons_counter,
            "processed_at_records": total_rows,
        }

        self.import_repo.update_completion(
            import_id=import_id,
            status=final_status,
            total_rows=total_rows,
            accepted_rows=accepted_rows,
            rejected_rows=rejected_rows,
            error_summary=summary,
            file_hash=file_hash,
        )

        return {
            "import_id": str(import_id),
            "status": final_status,
            "file_hash": file_hash,
            "total_rows": total_rows,
            "accepted_rows": accepted_rows,
            "rejected_rows": rejected_rows,
            "error_summary": summary,
        }

    def trigger_matching_workflow(self, import_id: UUID) -> bool:
        """Dispatches event to n8n Workflow B webhook or local matching engine."""
        self.import_repo.update_matching_status(import_id, "PROCESSING")
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    self.settings.N8N_MATCHING_WEBHOOK_URL,
                    json={"import_id": str(import_id)},
                    headers={"X-Webhook-Secret": self.settings.WEBHOOK_SECRET}
                )
                if resp.status_code in (200, 202):
                    return True
        except Exception:
            # If n8n webhook is not running or unreachable, state remains PROCESSING
            # and matching_service fallback can be run locally
            pass
        return False
