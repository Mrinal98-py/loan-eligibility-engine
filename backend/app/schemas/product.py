from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class LoanProductCreate(BaseModel):
    source_name: str
    source_url: str
    product_name: str
    product_type: str = "Personal Loan"
    interest_rate_min: Optional[Decimal] = None
    interest_rate_max: Optional[Decimal] = None
    min_monthly_income: Optional[Decimal] = Decimal("0.0")
    min_credit_score: Optional[int] = 300
    max_credit_score: Optional[int] = None
    min_age: Optional[int] = 18
    max_age: Optional[int] = 100
    eligible_employment_statuses: List[str] = Field(default_factory=lambda: ["Salaried", "Self-Employed", "Business"])
    eligibility_criteria_raw: Optional[str] = None
    eligibility_evidence: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class LoanProductResponse(BaseModel):
    id: UUID
    source_name: str
    source_url: str
    product_name: str
    product_type: str
    interest_rate_min: Optional[Decimal]
    interest_rate_max: Optional[Decimal]
    min_monthly_income: Optional[Decimal]
    min_credit_score: Optional[int]
    max_credit_score: Optional[int]
    min_age: Optional[int]
    max_age: Optional[int]
    eligible_employment_statuses: List[str]
    eligibility_evidence: Dict[str, Any]
    is_active: bool
    scraped_at: datetime
