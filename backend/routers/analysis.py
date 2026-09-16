"""backend/routers/analysis.py — contract analysis endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from analyzer import AnalysisError
from backend.analysis_service import EngineUnavailable, QuotaExceeded, run_analysis
from backend.deps import current_user_id
from backend.schemas import (
    AnalysisMeta,
    AnalyzeRequest,
    AnalyzeResponse,
    FlaggedClauseOut,
    UsageResponse,
)
from db_utils import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalyzeRequest,
    user_id: str = Depends(current_user_id),
) -> AnalyzeResponse:
    try:
        result, meta = run_analysis(
            user_id=user_id,
            text=payload.text,
            jurisdiction=payload.jurisdiction,
            force_engine=payload.force_engine,
        )
    except QuotaExceeded as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except EngineUnavailable:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Analysis engine unavailable — check that a valid GROQ_API_KEY or OPENAI_API_KEY is configured.",
        )
    except AnalysisError as exc:
        logger.error(f"LLM returned an unusable response: {exc}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Analysis engine returned an invalid response.")

    return AnalyzeResponse(
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        summary=result.summary,
        recommendation=result.recommendation,
        disclaimer=result.disclaimer,
        flagged_clauses=[
            FlaggedClauseOut(
                clause_text=c.clause_text,
                category=c.category,
                severity=c.severity,
                plain_english=c.plain_english,
                red_flag=c.red_flag,
            )
            for c in result.flagged_clauses
        ],
        meta=AnalysisMeta(**meta),
    )


@router.get("/usage", response_model=UsageResponse)
def usage(user_id: str = Depends(current_user_id)) -> UsageResponse:
    allowed, remaining, tier = check_rate_limit(user_id, "analysis")
    return UsageResponse(user_id=user_id, tier=tier, allowed=allowed, remaining=remaining)
