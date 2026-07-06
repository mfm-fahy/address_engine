from pydantic import BaseModel, Field
from typing import Optional, Any


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ToolCallInfo(BaseModel):
    tool: str
    arguments: dict
    result_summary: str
    duration_ms: float


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallInfo] = []
    token_usage: Optional[dict] = None
    model: str = ""


class BusinessInsights(BaseModel):
    summary: str
    metrics: dict = {}
    recommendations: list[str] = []
    follow_up_questions: list[str] = []


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
