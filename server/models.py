from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class RawOrder(BaseModel):
    source: str
    raw_data: dict
    phone: str
    customer_name: str = ""
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

class Customer(BaseModel):
    customer_id: str
    phone: str
    name: str = ""
    email: str = ""
    username: str = ""
    total_orders: int = 0
    total_spent: float = 0.0
    orders: list = []
    comments: list = []
    bills: list = []
    alerts: list = []
    last_activity: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Comment(BaseModel):
    customer_id: str = ""
    tenant_id: str = ""
    media_id: str = ""
    username: str = ""
    text: str = ""
    sentiment_score: float = 0.0
    sentiment_label: str = "neutral"
    is_negative: bool = False
    triggered_rule: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Alert(BaseModel):
    customer_id: str
    type: str
    message: str
    severity: str = "info"
    source: str = ""
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
