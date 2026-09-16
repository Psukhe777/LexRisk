"""backend/schemas.py — request/response contracts for the REST API."""

from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    llm_configured: bool


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw contract or ToS text")
    jurisdiction: Optional[str] = Field(
        default=None, description="Jurisdiction key, e.g. 'federal', 'california'"
    )
    force_engine: Optional[str] = Field(
        default=None, pattern="^(groq|openai)$", description="Override engine selection"
    )


class FlaggedClauseOut(BaseModel):
    clause_text: str
    category: str
    severity: str
    plain_english: str
    red_flag: str


class AnalysisMeta(BaseModel):
    engine_used: str
    contract_type: str
    cache_hit: bool
    processing_time_ms: int
    nlp_filtered: bool
    nlp_chunks_analyzed: int
    text_truncated: bool
    truncated_at_chars: Optional[int] = None


class AnalyzeResponse(BaseModel):
    risk_score: int
    risk_level: str
    summary: str
    recommendation: str
    disclaimer: str
    flagged_clauses: list[FlaggedClauseOut]
    meta: AnalysisMeta


class UsageResponse(BaseModel):
    user_id: str
    tier: str
    allowed: bool
    remaining: int
