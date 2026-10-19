import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from backend.app.settings import Settings, get_settings
from backend.app.models.base import User, Match, LoanProduct, Notification
from backend.app.repositories.import_repo import ImportRepository
from backend.app.repositories.match_repo import MatchRepository
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.schemas.notification import NotificationBatchSummary


class NotificationSafetyError(Exception):
    """Raised when an unsafe recipient address or configuration is detected."""
    pass


class NotificationService:
    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()
        self.import_repo = ImportRepository(db)
        self.match_repo = MatchRepository(db)
        self.notification_repo = NotificationRepository(db)

    def resolve_recipient_email(self, user_csv_email: str) -> str:
        """
        STRICT RECIPIENT RESOLUTION ENFORCEMENT:
        In test mode (default), user CSV email is NEVER used.
        Only an address from TEST_EMAIL_RECIPIENTS allowlist is returned.
        """
        if self.settings.DELIVERY_MODE != "production" or not self.settings.ALLOW_REAL_RECIPIENTS:
            test_recipients = self.settings.test_recipient_list
            if not test_recipients:
                raise NotificationSafetyError("DELIVERY_MODE is 'test' but TEST_EMAIL_RECIPIENTS is empty or unconfigured.")
            # Deterministic alias mapping or round-robin to configured test inbox
            return test_recipients[0]

        # In production mode (only if ALLOW_REAL_RECIPIENTS is True)
        if not self.settings.ALLOW_REAL_RECIPIENTS:
            raise NotificationSafetyError("ALLOW_REAL_RECIPIENTS is False. Refusing to send to real recipient.")
        return user_csv_email

    def format_email_body(self, user: User, matches: List[Match]) -> Tuple[str, str]:
        """Generates plain-text and HTML notification bodies with disclaimers and product terms."""
        user_display = user.name or user.external_user_id
        product_rows_text = []
        product_rows_html = []

        for m in matches:
            p = m.product
            rate_info = f"{p.interest_rate_min}% - {p.interest_rate_max}% p.a." if p.interest_rate_min and p.interest_rate_max else "Published bank rates apply"
            reasons_summary = "; ".join(r.get("message", "") for r in m.match_reasons)

            product_rows_text.append(
                f"- Product: {p.product_name} ({p.source_name})\n"
                f"  Indicative Interest Rate: {rate_info}\n"
                f"  Eligibility Criteria Met: {reasons_summary}\n"
                f"  Product Page: {p.source_url}\n"
            )

            product_rows_html.append(f"""
                <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background-color: #f8fafc;">
                    <h3 style="margin-top: 0; color: #1e293b;">{p.product_name}</h3>
                    <p style="margin: 4px 0; color: #475569;"><strong>Lender:</strong> {p.source_name}</p>
                    <p style="margin: 4px 0; color: #475569;"><strong>Indicative Rate:</strong> {rate_info}</p>
                    <p style="margin: 4px 0; color: #475569;"><strong>Matched Criteria:</strong> {reasons_summary}</p>
                    <p style="margin-top: 8px;"><a href="{p.source_url}" style="color: #2563eb; text-decoration: underline;" target="_blank">View Official Product Page</a></p>
                </div>
            """)

        text_body = f"""Hello {user_display},

Good news! Based on our automated eligibility criteria analysis, you may be eligible for the following personal loan products:

{"".join(product_rows_text)}

--------------------------------------------------------------------------------
IMPORTANT REGULATORY DISCLAIMER:
These matched products are indicative and based solely on public criteria published by lenders. 
This notification does NOT constitute a credit offer, loan approval, or a guarantee that the lender will approve your application. Final terms and interest rates are determined exclusively by the lending institution upon submission of a formal loan application and verification of documents.
--------------------------------------------------------------------------------
"""

        html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #0f172a;">Personal Loan Eligibility Matches</h2>
    <p>Hello <strong>{user_display}</strong>,</p>
    <p>Based on our automated matching analysis against publicly published bank criteria, here are the personal loan products you may be eligible for:</p>
    
    {"".join(product_rows_html)}
    
    <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px; margin-top: 24px; font-size: 13px; color: #991b1b;">
        <strong>IMPORTANT REGULATORY DISCLAIMER:</strong><br>
        Matches are indicative based on published eligibility criteria. This notification does not constitute a loan offer, approval, or guarantee. Final credit approval depends solely on individual lender verification.
    </div>
</body>
</html>
"""
        return text_body, html_body

    def dispatch_email(
        self,
        recipient: str,
        subject: str,
        text_body: str,
        html_body: str
    ) -> str:
        """Sends email via Amazon SES or local preview logger if SES not configured."""
        if self.settings.ENVIRONMENT == "production" or (self.settings.AWS_ACCESS_KEY_ID and "mock" not in self.settings.AWS_ACCESS_KEY_ID):
            ses_client = boto3.client(
                "ses",
                region_name=self.settings.AWS_REGION,
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
            )
            response = ses_client.send_email(
                Source=self.settings.SES_FROM_EMAIL,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )
            return response.get("MessageId", f"ses-{uuid.uuid4()}")
        else:
            # Local simulation / preview mode
            mock_message_id = f"local-mock-ses-{uuid.uuid4()}"
            return mock_message_id

    def process_notifications_for_import(self, import_id: uuid.UUID, max_dispatch: Optional[int] = None) -> NotificationBatchSummary:
        """
        Processes notifications for users with confirmed matches in this import.
        Uses single-query grouping to eliminate N+1 queries.
        Enforces idempotency and strict test recipient override.
        """
        import collections
        self.import_repo.update_notification_status(import_id, "PROCESSING")

        # 1. Fetch all matches with user and product in a single query
        all_matches = self.match_repo.get_by_import_id(import_id)
        matches_by_user = collections.defaultdict(list)
        users_by_id = {}
        for m in all_matches:
            matches_by_user[m.user_id].append(m)
            users_by_id[m.user_id] = m.user

        existing_notifications = {
            n.user_id: n for n in self.notification_repo.get_by_import_id(import_id)
        }

        sent_count = 0
        failed_count = 0
        queued_count = 0
        recipients_used = set()

        # Limit dispatch if max_dispatch is passed (useful for rapid demo sampling)
        user_ids = list(matches_by_user.keys())
        if max_dispatch is not None:
            user_ids = user_ids[:max_dispatch]

        for uid in user_ids:
            if uid in existing_notifications and existing_notifications[uid].status == "SENT":
                continue

            user = users_by_id[uid]
            user_matches = matches_by_user[uid]

            # Safe recipient resolution
            try:
                safe_recipient = self.resolve_recipient_email(user.email)
            except NotificationSafetyError as e:
                self.notification_repo.create(
                    import_id=import_id,
                    user_id=user.id,
                    delivery_mode=self.settings.DELIVERY_MODE,
                    test_recipient="BLOCKED_BY_SAFETY_POLICY",
                    matched_products_count=len(user_matches),
                    status="FAILED",
                    error_message=str(e),
                )
                failed_count += 1
                continue

            recipients_used.add(safe_recipient)
            queued_count += 1

            notif_record = self.notification_repo.create(
                import_id=import_id,
                user_id=user.id,
                delivery_mode=self.settings.DELIVERY_MODE,
                test_recipient=safe_recipient,
                matched_products_count=len(user_matches),
                status="QUEUED"
            )

            text_body, html_body = self.format_email_body(user, user_matches)
            subject = f"Personal Loan Matches ({len(user_matches)} indicative offers found)"

            try:
                msg_id = self.dispatch_email(
                    recipient=safe_recipient,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body
                )
                self.notification_repo.mark_sent(notif_record.id, provider_message_id=msg_id)
                sent_count += 1
            except Exception as e:
                self.notification_repo.mark_failed(notif_record.id, error_message=str(e))
                failed_count += 1

        self.import_repo.update_notification_status(import_id, "COMPLETED")

        return NotificationBatchSummary(
            import_id=import_id,
            total_eligible_users=len(matches_by_user),
            notifications_queued=queued_count,
            notifications_sent=sent_count,
            notifications_failed=failed_count,
            delivery_mode=self.settings.DELIVERY_MODE,
            test_recipients_used=list(recipients_used),
        )

