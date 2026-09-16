"""
backend/analysis_service.py — UI-free orchestration of a single analysis request.

This is the Streamlit analysis flow from main.py, minus Streamlit:
  quota check → cache lookup → analyze → cache store → quota decrement → logging

Quota behaviour follows audit FIX 5: increment_usage() runs on EVERY accepted
request, cache hit or not. The cache ratio is tracked via analysis_history.cache_hit.
"""

import logging
import time
from typing import Any, Optional

from analyzer import AnalysisError, AnalysisResult, ClauseAnalyzer, FlaggedClause
from backend.config import get_settings
from db_utils import (
    UNLIMITED,
    cache_analysis,
    check_rate_limit,
    get_cached_analysis,
    get_contract_hash,
    get_or_create_user,
    get_tier_limits,
    increment_usage,
    log_analysis,
    track_redlined_clause,
)
from jurisdictional_rules import Jurisdiction

logger = logging.getLogger(__name__)

CHARS_PER_PAGE = 3000

_analyzer: Optional[ClauseAnalyzer] = None


class QuotaExceeded(Exception):
    """Raised when the caller has no daily analyses left."""


class EngineUnavailable(Exception):
    """Raised when every LLM provider failed (bad key, outage, rate limit)."""


class ContractTooLarge(Exception):
    """Raised when the contract exceeds the caller's tier size limits."""


def resolve_jurisdiction(value: Optional[str]) -> Jurisdiction:
    if not value:
        return Jurisdiction.FEDERAL
    try:
        return Jurisdiction(value.strip().lower())
    except ValueError:
        logger.warning(f"Unknown jurisdiction '{value}' - defaulting to FEDERAL")
        return Jurisdiction.FEDERAL


def get_analyzer() -> ClauseAnalyzer:
    """Process-wide analyzer (loads the NLP model once)."""
    global _analyzer
    if _analyzer is None:
        settings = get_settings()
        _analyzer = ClauseAnalyzer(enable_nlp_filter=settings.enable_nlp_filter)
    return _analyzer


def estimate_page_count(text: str) -> int:
    return max(1, -(-len(text) // CHARS_PER_PAGE))


def result_to_payload(result: AnalysisResult) -> dict[str, Any]:
    return {
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "summary": result.summary,
        "recommendation": result.recommendation,
        "disclaimer": result.disclaimer,
        "engine_used": result.engine_used,
        "contract_type": result.contract_type,
        "nlp_filtered": result.nlp_filtered,
        "nlp_chunks_analyzed": result.nlp_chunks_analyzed,
        "text_truncated": result.text_truncated,
        "truncated_at_chars": result.truncated_at_chars,
        "flagged_clauses": [
            {
                "clause_text": c.clause_text,
                "category": c.category,
                "severity": c.severity,
                "plain_english": c.plain_english,
                "red_flag": c.red_flag,
            }
            for c in result.flagged_clauses
        ],
    }


def payload_to_result(payload: dict[str, Any]) -> AnalysisResult:
    return AnalysisResult(
        risk_score=payload["risk_score"],
        risk_level=payload["risk_level"],
        flagged_clauses=[FlaggedClause(**c) for c in payload.get("flagged_clauses", [])],
        summary=payload.get("summary", ""),
        recommendation=payload.get("recommendation", "NEGOTIATE"),
        raw_response="",
        disclaimer=payload.get("disclaimer", ""),
        engine_used=payload.get("engine_used", "cache"),
        contract_type=payload.get("contract_type", "Unknown"),
        nlp_filtered=payload.get("nlp_filtered", False),
        nlp_chunks_analyzed=payload.get("nlp_chunks_analyzed", 0),
        text_truncated=payload.get("text_truncated", False),
        truncated_at_chars=payload.get("truncated_at_chars"),
    )


def run_analysis(
    user_id: str,
    text: str,
    jurisdiction: Optional[str] = None,
    force_engine: Optional[str] = None,
) -> tuple[AnalysisResult, dict[str, Any]]:
    """Analyze a contract for a user. Returns (result, meta)."""
    if not text or not text.strip():
        raise ValueError("Contract text cannot be empty.")

    get_or_create_user(user_id)
    allowed, _remaining, tier = check_rate_limit(user_id, "analysis")
    if not allowed:
        raise QuotaExceeded("Daily analysis limit reached for your current tier.")

    # Size caps come from the tier_limits table — never a hardcoded dict.
    limits = get_tier_limits(tier)
    max_chars = limits["max_text_chars"]
    max_pages = limits["max_pages_per_pdf"]
    page_count = estimate_page_count(text)

    if max_chars != UNLIMITED and len(text) > max_chars:
        raise ContractTooLarge(
            f"Contract is {len(text):,} characters; the {tier} tier allows {max_chars:,}."
        )
    if max_pages != UNLIMITED and page_count > max_pages:
        raise ContractTooLarge(
            f"Contract is ~{page_count} pages; the {tier} tier allows {max_pages}."
        )

    resolved = resolve_jurisdiction(jurisdiction)
    contract_hash = get_contract_hash(f"{resolved.value}::{text}")

    started = time.perf_counter()
    cached = get_cached_analysis(contract_hash)

    if cached and cached.get("analysis_result"):
        result = payload_to_result(cached["analysis_result"])
        cache_hit = True
        processing_time_ms = 0
    else:
        analyzer = get_analyzer()
        analyzer.jurisdiction = resolved
        try:
            result = analyzer.analyze(text, force_engine=force_engine)
        except (ValueError, AnalysisError):
            raise
        except Exception as exc:
            logger.error(f"All analysis engines failed: {exc}")
            raise EngineUnavailable(str(exc)) from exc
        cache_hit = False
        processing_time_ms = int((time.perf_counter() - started) * 1000)

        cache_analysis(
            contract_hash,
            len(text),
            result.risk_score,
            result.risk_level,
            result_to_payload(result),
            result.engine_used,
        )

    # FIX 5: quota decrements on cache hits too.
    increment_usage(user_id, "analysis", pages=page_count, text_chars=len(text))

    log_analysis(
        user_id,
        contract_hash,
        len(text),
        page_count,
        result.risk_score,
        result.risk_level,
        result.engine_used,
        cache_hit,
        processing_time_ms,
    )

    for clause in result.flagged_clauses:
        track_redlined_clause(clause.category, clause.severity, clause.clause_text, contract_hash)

    meta = {
        "engine_used": result.engine_used,
        "contract_type": result.contract_type,
        "cache_hit": cache_hit,
        "processing_time_ms": processing_time_ms,
        "nlp_filtered": result.nlp_filtered,
        "nlp_chunks_analyzed": result.nlp_chunks_analyzed,
        "text_truncated": result.text_truncated,
        "truncated_at_chars": result.truncated_at_chars,
    }
    return result, meta
