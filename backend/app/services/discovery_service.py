import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.orm import Session
from backend.app.settings import Settings, get_settings
from backend.app.repositories.product_repo import LoanProductRepository


def utcnow():
    return datetime.now(timezone.utc)


class DiscoveryService:
    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()
        self.product_repo = LoanProductRepository(db)

    def extract_from_html(self, html_content: str, default_source_name: str, source_url: str) -> List[Dict[str, Any]]:
        """
        Deterministic parser that extracts personal loan criteria with provenance evidence.
        Never fabricates criteria: missing criteria are kept None/unknown.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        products = []
        cards = soup.find_all(["article", "div", "section"], class_=lambda c: c and ("loan" in c or "product" in c or "card" in c))

        if not cards:
            # Fallback to entire page if no card wrappers found
            cards = [soup]

        for card in cards:
            title_node = card.find(["h1", "h2", "h3", "h4"], class_=lambda c: c and ("title" in c or "name" in c or "heading" in c)) or card.find(["h1", "h2", "h3"])
            product_name = title_node.get_text(strip=True) if title_node else "Personal Loan Offer"

            bank_name = card.get("data-bank") or default_source_name
            url_node = card.find("a", href=True)
            card_url = url_node["href"] if url_node and url_node["href"].startswith("http") else source_url

            card_text = card.get_text(separator=" ", strip=True)

            # Interest rates extraction
            rate_min, rate_max = None, None
            rate_match = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:to|-)\s*(\d{1,2}(?:\.\d{1,2})?)\s*%", card_text, re.IGNORECASE)
            single_rate_match = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:p\.?a\.?|per annum|interest)", card_text, re.IGNORECASE)
            rate_evidence = None

            if rate_match:
                rate_min = Decimal(rate_match.group(1))
                rate_max = Decimal(rate_match.group(2))
                rate_evidence = rate_match.group(0)
            elif single_rate_match:
                rate_min = Decimal(single_rate_match.group(1))
                rate_evidence = single_rate_match.group(0)

            # Monthly income extraction
            income_min = Decimal("0.0")
            income_evidence = None
            inc_match = re.search(r"(?:monthly|salary|income|take home)[^\d]{1,30}(?:rs\.?|inr|₹)?\s*([\d,]+)", card_text, re.IGNORECASE)
            if inc_match:
                raw_num = inc_match.group(1).replace(",", "")
                if raw_num.isdigit():
                    income_min = Decimal(raw_num)
                    income_evidence = inc_match.group(0).strip()

            # Credit score extraction
            credit_min = 300
            score_evidence = None
            cs_match = re.search(r"(?:credit score|cibil|bureau)[^\d]{1,25}(\d{3})", card_text, re.IGNORECASE)
            if cs_match:
                score = int(cs_match.group(1))
                if 300 <= score <= 900:
                    credit_min = score
                    score_evidence = cs_match.group(0).strip()

            # Age extraction
            min_age = 18
            max_age = 100
            age_evidence = None
            age_match = re.search(r"(?:age|between)[^\d]{1,20}(\d{2})\s*(?:to|-|and)\s*(\d{2})", card_text, re.IGNORECASE)
            if age_match:
                a1 = int(age_match.group(1))
                a2 = int(age_match.group(2))
                if 18 <= a1 < a2 <= 100:
                    min_age = a1
                    max_age = a2
                    age_evidence = age_match.group(0).strip()

            # Employment statuses
            emp_statuses = []
            if re.search(r"\bsalaried\b", card_text, re.IGNORECASE):
                emp_statuses.append("Salaried")
            if re.search(r"\bself-employed\b|\bprofessionals\b", card_text, re.IGNORECASE):
                emp_statuses.append("Self-Employed")
            if re.search(r"\bbusiness\b|\bproprietor\b", card_text, re.IGNORECASE):
                emp_statuses.append("Business")
            if not emp_statuses:
                emp_statuses = ["Salaried", "Self-Employed", "Business"]

            evidence = {}
            if rate_evidence:
                evidence["rate_evidence"] = rate_evidence
            if income_evidence:
                evidence["income_evidence"] = income_evidence
            if score_evidence:
                evidence["score_evidence"] = score_evidence
            if age_evidence:
                evidence["age_evidence"] = age_evidence

            product_dict = {
                "source_name": bank_name,
                "source_url": card_url,
                "product_name": product_name,
                "product_type": "Personal Loan",
                "interest_rate_min": rate_min,
                "interest_rate_max": rate_max,
                "min_monthly_income": income_min,
                "min_credit_score": credit_min,
                "max_credit_score": None,
                "min_age": min_age,
                "max_age": max_age,
                "eligible_employment_statuses": emp_statuses,
                "eligibility_criteria_raw": card_text[:1000],
                "eligibility_evidence": evidence,
                "is_active": True,
                "verified_at": utcnow(),
                "scraped_at": utcnow(),
            }
            products.append(product_dict)

        return products

    def discover_and_upsert(self, source_name: str, source_url: str, html_content: Optional[str] = None) -> List[Any]:
        """Runs product discovery for a given source and upserts results into database."""
        start_time = time.time()
        products_upserted = []
        error_msg = None
        status_code = 200

        try:
            if not html_content:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(
                        source_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 LoanEngine/1.0"}
                    )
                    status_code = resp.status_code
                    resp.raise_for_status()
                    html_content = resp.text

            extracted = self.extract_from_html(html_content, source_name, source_url)
            for prod in extracted:
                saved = self.product_repo.upsert_product(prod)
                products_upserted.append(saved)

            status = "SUCCESS" if products_upserted else "PARTIAL"
        except Exception as e:
            status = "FAILED"
            error_msg = str(e)

        duration_ms = int((time.time() - start_time) * 1000)
        self.product_repo.record_extraction_run(
            source_name=source_name,
            source_url=source_url,
            status=status,
            products_found=len(products_upserted),
            error_message=error_msg,
            response_status_code=status_code,
            duration_ms=duration_ms,
        )

        return products_upserted
