from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class UserProfile(BaseModel):
    id: UUID
    external_user_id: str
    name: Optional[str] = None
    email: str
    monthly_income: Decimal
    credit_score: int
    employment_status: str
    age: int
    created_at: datetime


class ValidatedUserRow(BaseModel):
    external_user_id: str
    name: Optional[str]
    email: str
    monthly_income: Decimal
    credit_score: int
    employment_status: str
    age: int
