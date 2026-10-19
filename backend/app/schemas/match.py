from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class MatchingWebhookRequest(BaseModel):
    import_id: UUID
    secret: Optional[str] = None


class MatchReasonItem(BaseModel):
    criterion: str
    rule: str
    user_value: Any
    threshold: Any
    passed: bool


class MatchResponse(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    product_name: str
    source_name: str
    interest_rate_min: Optional[Decimal]
    interest_rate_max: Optional[Decimal]
    match_score: Decimal
    match_reasons: List[Dict[str, Any]]
    status: str
    created_at: datetime


class MatchingFunnelMetrics(BaseModel):
    import_id: UUID
    users_evaluated: int
    active_products: int
    theoretical_pairs: int
    pairs_after_sql_prefilter: int
    sql_reduction_percentage: float
    deterministic_matches_found: int
    llm_evaluations_performed: int
    llm_evaluations_avoided: int
    duration_ms: int
