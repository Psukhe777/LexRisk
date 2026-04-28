"""""
LexRisk v2.0 Streamlit frontend.

This app orchestrates the modular backend for:
- NLP semantic pre-filtering
- PostgreSQL usage tracking
- Jurisdiction-aware scoring
- Civil liability estimation
- Industry benchmarking
- PDF litigation shield export
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import pdfplumber
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(
    page_title="Lexrisk ⚖️",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

from analyzer import AnalysisResult, ClauseAnalyzer, FlaggedClause
from circuit_breaker import CircuitBreakerOpen, get_openai_circuit_breaker
from competitor_benchmark import (
    IndustryType,
    compare_to_industry,
    create_benchmark_radar_chart,
    get_available_industries,
    get_industry_by_name,
)
from db_utils import (
    cache_analysis,
    check_rate_limit,
    get_cached_analysis,
    get_contract_hash,
    get_or_create_user,
    get_usage_stats,
    increment_usage,
    init_db_pool,
    log_analysis,
    track_redlined_clause,
)
from jurisdictional_rules import (
    Jurisdiction,
    check_missing_disclosures,
    get_jurisdiction_by_name,
    get_jurisdiction_display_names,
    get_jurisdiction_profile,
    get_required_disclosures,
)
from liability_calculator import LiabilityCalculator
from nlp_engine import get_nlp_engine
from pdf_export import LitigationShieldPDF
from redliner import get_redlined_html, get_redlining_summary

try:
    from telemetry import log_analysis_telemetry, log_error_telemetry

    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False

    def log_analysis_telemetry(*args, **kwargs):
        return None

    def log_error_telemetry(*args, **kwargs):
        return None


MAX_FILE_SIZE_MB = 25

TIER_LIMITS = {
    "free": {
        "name": "Free",
        "max_pages": 50,
        "max_text_chars": 100000,
        "daily_analyses": 3,
    },
    "pro": {
        "name": "Pro",
        "max_pages": 500,
        "max_text_chars": 1000000,
        "daily_analyses": 50,
    },
    "business": {
        "name": "Business",
        "max_pages": -1,
        "max_text_chars": -1,
        "daily_analyses": -1,
    },
}

DEFAULT_AFFECTED_USERS = 1000


@st.cache_resource(show_spinner=False)
def bootstrap_nlp_engine():
    """Load the NLP engine exactly once per server process."""
    return get_nlp_engine()


@st.cache_resource(show_spinner=False)
def bootstrap_pdf_generator():
    """Reuse the PDF generator across reruns."""
    return LitigationShieldPDF()


@st.cache_resource(show_spinner=False)
def bootstrap_db():
    """Initialize the DB pool once if DATABASE_URL is configured."""
    return init_db_pool()


bootstrap_db()
bootstrap_nlp_engine()


def init_session_state() -> None:
    defaults = {
        "contract_text": "",
        "analysis_complete": False,
        "last_analysis_result": None,
        "last_analysis_meta": {},
        "uploaded_contract_name": "Untitled Contract",
        "uploaded_page_count": 0,
        "affected_users": DEFAULT_AFFECTED_USERS,
        "benchmark_industry_name": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_tier_info(tier: str) -> Dict[str, Any]:
    return TIER_LIMITS.get((tier or "free").lower(), TIER_LIMITS["free"])


def get_user_id() -> str:
    """Use the real client IP when available, otherwise fall back to a stable session ID."""
    try:
        headers = st.context.headers
        forwarded_for = headers.get("X-Forwarded-For") or headers.get("X-Real-IP")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return f"ip_{client_ip}"
    except Exception as exc:
        logger.debug("Unable to resolve forwarded IP headers: %s", exc)

    if "user_id" not in st.session_state:
        st.session_state.user_id = f"session_{uuid.uuid4()}"
    return st.session_state.user_id


def normalize_for_storage(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return normalize_for_storage(asdict(value))
    if isinstance(value, dict):
        return {key: normalize_for_storage(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_for_storage(item) for item in value]
    return value


def resolve_jurisdiction(value: Any) -> Jurisdiction:
    if isinstance(value, Jurisdiction):
        return value

    if isinstance(value, str):
        try:
            return Jurisdiction(value.lower())
        except Exception:
            by_name = get_jurisdiction_by_name(value)
            if by_name:
                return by_name

    return Jurisdiction.FEDERAL


def hydrate_analysis_result(payload: Dict[str, Any]) -> AnalysisResult:
    flagged_clauses = [
        FlaggedClause(
            clause_text=clause.get("clause_text", ""),
            category=clause.get("category", "Unknown"),
            severity=clause.get("severity", "MEDIUM"),
            plain_english=clause.get("plain_english", ""),
            red_flag=clause.get("red_flag", ""),
        )
        for clause in payload.get("flagged_clauses", [])
    ]

    return AnalysisResult(
        risk_score=payload.get("risk_score", 0),
        risk_level=payload.get("risk_level", "LOW"),
        flagged_clauses=flagged_clauses,
        summary=payload.get("summary", ""),
        recommendation=payload.get("recommendation", "NEGOTIATE"),
        raw_response=payload.get("raw_response", ""),
        disclaimer=payload.get("disclaimer", ""),
        engine_used=payload.get("engine_used", "unknown"),
        contract_type=payload.get("contract_type", "unknown"),
        nlp_filtered=payload.get("nlp_filtered", False),
        nlp_filter_ratio=payload.get("nlp_filter_ratio", 0.0),
        nlp_chunks_analyzed=payload.get("nlp_chunks_analyzed", 0),
        nlp_max_similarity=payload.get("nlp_max_similarity", 0.0),
        jurisdiction=resolve_jurisdiction(payload.get("jurisdiction")),
        jurisdictional_score_adjustment=payload.get("jurisdictional_score_adjustment", 0),
    )


def get_api_keys() -> Tuple[Optional[str], Optional[str]]:
    openai_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    groq_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    return openai_key, groq_key


def get_contract_cache_key(contract_text: str, jurisdiction: Jurisdiction) -> str:
    return get_contract_hash(f"{jurisdiction.value}::{contract_text}")


def validate_pdf_upload(uploaded_file, tier: str) -> tuple[bool, Optional[str]]:
    """
    Validate PDF upload against strict limits.
    Returns: (is_valid, error_message)
    """
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return False, f"File size ({file_size_mb:.1f}MB) exceeds maximum ({MAX_FILE_SIZE_MB}MB)"

    tier_info = get_tier_info(tier)
    max_pages = tier_info.get("max_pages", 50)

    try:
        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            page_count = len(pdf.pages)
            if max_pages != -1 and page_count > max_pages:
                return False, (
                    f"PDF has {page_count} pages but your {tier_info['name']} plan "
                    f"allows {max_pages} pages"
                )
    except Exception as exc:
        return False, f"Failed to read PDF: {exc}"
    finally:
        uploaded_file.seek(0)

    return True, None


def extract_pdf_text(uploaded_file, tier: str) -> tuple[Optional[str], Optional[str], int]:
    """
    Extract text from PDF with memory-efficient processing.
    Returns: (extracted_text, error_message, page_count)
    """
    try:
        tier_info = get_tier_info(tier)
        max_pages = tier_info.get("max_pages", 50)
        max_chars = tier_info.get("max_text_chars", 100000)

        text_parts = []
        total_chars = 0

        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            page_count = len(pdf.pages)
            pages_to_process = min(page_count, max_pages) if max_pages != -1 else page_count

            for page in pdf.pages[:pages_to_process]:
                if max_chars != -1 and total_chars >= max_chars:
                    break

                page_text = page.extract_text() or ""

                if max_chars != -1:
                    remaining = max_chars - total_chars
                    page_text = page_text[:remaining]

                text_parts.append(page_text)
                total_chars += len(page_text)

            extracted_text = "\n\n".join(text_parts)

            if max_chars != -1 and len(extracted_text) > max_chars:
                extracted_text = extracted_text[:max_chars]
                logger.warning("Extracted text truncated to %,d characters", max_chars)

            return extracted_text, None, page_count
    except Exception as exc:
        logger.error("PDF extraction error: %s", exc)
        return None, f"Failed to extract text: {exc}", 0
    finally:
        uploaded_file.seek(0)


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_contract_cached(
    contract_text: str,
    jurisdiction_name: str,
    provider: str = "auto",
) -> AnalysisResult:
    """
    Cached contract analysis.

    Including `jurisdiction_name` in the signature ensures cache busting
    whenever the legal context changes.
    """
    jurisdiction = resolve_jurisdiction(jurisdiction_name)
    openai_key, groq_key = get_api_keys()

    if provider == "openai":
        if not openai_key:
            raise ValueError("Missing OPENAI_API_KEY for OpenAI analysis.")
        analyzer = ClauseAnalyzer(
            openai_key=openai_key,
            provider="openai",
            jurisdiction=jurisdiction,
        )
    elif provider == "groq":
        if not groq_key:
            raise ValueError("Missing GROQ_API_KEY for Groq analysis.")
        analyzer = ClauseAnalyzer(
            groq_key=groq_key,
            provider="groq",
            jurisdiction=jurisdiction,
        )
    else:
        analyzer = ClauseAnalyzer(
            openai_key=openai_key,
            groq_key=groq_key,
            provider="auto",
            jurisdiction=jurisdiction,
        )

    return analyzer.analyze(contract_text)


def analyze_with_circuit_breaker(
    contract_text: str,
    jurisdiction_name: str,
) -> tuple[AnalysisResult, Dict[str, Any]]:
    """
    Prefer OpenAI for long/complex documents, protected by the circuit breaker.
    Fall back to Groq if OpenAI is unavailable or the breaker is open.
    """
    start_time = time.time()
    text_length = len(contract_text)
    preferred_provider = "openai" if text_length > 4500 else "groq"

    meta: Dict[str, Any] = {
        "provider_used": preferred_provider,
        "breaker_state": "n/a",
        "failover": False,
    }

    if preferred_provider == "openai":
        breaker = get_openai_circuit_breaker()
        try:
            result = breaker.call(
                analyze_contract_cached,
                contract_text,
                jurisdiction_name,
                "openai",
            )
            meta["provider_used"] = result.engine_used or "openai"
            meta["breaker_state"] = breaker.get_state()
        except CircuitBreakerOpen:
            result = analyze_contract_cached(contract_text, jurisdiction_name, "groq")
            meta["provider_used"] = result.engine_used or "groq"
            meta["breaker_state"] = "open"
            meta["failover"] = True
        except Exception:
            logger.exception("OpenAI analysis failed, attempting Groq fallback")
            result = analyze_contract_cached(contract_text, jurisdiction_name, "groq")
            meta["provider_used"] = result.engine_used or "groq"
            meta["breaker_state"] = breaker.get_state()
            meta["failover"] = True
    else:
        result = analyze_contract_cached(contract_text, jurisdiction_name, "groq")
        meta["provider_used"] = result.engine_used or "groq"

    meta["processing_time_ms"] = int((time.time() - start_time) * 1000)
    return result, meta


def estimate_manual_page_count(contract_text: str) -> int:
    return max(1, len(contract_text) // 3000 + 1)


def default_benchmark_for_contract(contract_type: str) -> IndustryType:
    mapping = {
        "social_media": IndustryType.SOCIAL_MEDIA,
        "saas": IndustryType.SAAS,
        "b2b": IndustryType.ENTERPRISE_B2B,
        "consumer": IndustryType.CONSUMER_APP,
    }
    return mapping.get((contract_type or "").lower(), IndustryType.CONSUMER_APP)


@st.cache_data(show_spinner=False)
def calculate_liability_cached(
    flagged_clauses: list[Dict[str, Any]],
    jurisdiction_name: str,
    contract_type: str,
    affected_users: int,
) -> Dict[str, Any]:
    jurisdiction = resolve_jurisdiction(jurisdiction_name)
    calculator = LiabilityCalculator(jurisdiction)
    report = calculator.calculate_liability(
        flagged_clauses=flagged_clauses,
        contract_type=contract_type or "consumer",
        estimated_affected_users=affected_users,
    )
    return normalize_for_storage(report)


def render_summary_tab(
    result: AnalysisResult,
    result_dict: Dict[str, Any],
    contract_text: str,
) -> None:
    jurisdiction = result.jurisdiction or Jurisdiction.FEDERAL
    profile = get_jurisdiction_profile(jurisdiction)
    missing_disclosures = check_missing_disclosures(contract_text, jurisdiction)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Risk Score", f"{result.risk_score}/100")
    metric_2.metric("Risk Level", result.risk_level)
    metric_3.metric("Recommendation", result.recommendation)
    metric_4.metric("Flagged Clauses", len(result.flagged_clauses))

    st.progress(min(max(result.risk_score, 0), 100) / 100)
    st.info(result.summary)

    insight_1, insight_2 = st.columns([1.3, 1])

    with insight_1:
        st.subheader("Flagged Clauses")
        if result.flagged_clauses:
            for index, clause in enumerate(result.flagged_clauses, start=1):
                with st.expander(
                    f"{index}. {clause.category} | {clause.severity}",
                    expanded=clause.severity in {"CRITICAL", "HIGH"},
                ):
                    st.markdown("**Clause Text**")
                    st.code(clause.clause_text)
                    st.markdown("**Plain English**")
                    st.write(clause.plain_english)
                    st.markdown("**Legal Concern**")
                    st.warning(clause.red_flag)
        else:
            st.success("No predatory clauses were detected.")

    with insight_2:
        st.subheader("Jurisdiction Profile")
        st.write(profile.display_name)
        st.caption(profile.description)

        st.markdown("**Required Disclosures**")
        for disclosure in get_required_disclosures(jurisdiction):
            st.write(f"• {disclosure}")

        st.markdown("**Missing Disclosures**")
        if missing_disclosures:
            for disclosure in missing_disclosures:
                st.error(disclosure)
        else:
            st.success("No missing required disclosures detected.")

        st.markdown("**Engine Diagnostics**")
        st.caption(
            f"Engine: {result.engine_used} | "
            f"NLP filtered: {result.nlp_filtered} | "
            f"Chunks analyzed: {result.nlp_chunks_analyzed}"
        )
        if result.nlp_filtered:
            st.caption(
                f"Filter ratio: {result.nlp_filter_ratio:.2%} | "
                f"Max similarity: {result.nlp_max_similarity:.3f}"
            )

    st.warning(f"Legal Notice: {result.disclaimer}")


def render_redlines_tab(result_dict: Dict[str, Any], contract_text: str) -> None:
    summary_html = get_redlining_summary(result_dict["flagged_clauses"])
    st.markdown(summary_html, unsafe_allow_html=True)
    st.divider()
    redlined_html = get_redlined_html(contract_text, result_dict["flagged_clauses"])
    st.markdown(redlined_html, unsafe_allow_html=True)


def render_liability_tab(
    result: AnalysisResult,
    result_dict: Dict[str, Any],
) -> Dict[str, Any]:
    st.session_state.affected_users = st.number_input(
        "Estimated affected users / counterparties",
        min_value=1,
        max_value=10000000,
        value=int(st.session_state.affected_users),
        step=100,
        help="Used to estimate statutory damages and class action exposure.",
    )

    liability_report = calculate_liability_cached(
        result_dict["flagged_clauses"],
        (result.jurisdiction or Jurisdiction.FEDERAL).value,
        result.contract_type,
        int(st.session_state.affected_users),
    )

    top_1, top_2, top_3 = st.columns(3)
    top_1.metric("Expected Liability", f"${liability_report['total_liability_expected']:,}")
    top_2.metric(
        "Liability Range",
        f"${liability_report['total_liability_min']:,} - ${liability_report['total_liability_max']:,}",
    )
    top_3.metric(
        "Class Action Exposure",
        "Yes" if liability_report["class_action_applicable"] else "No",
    )

    summary_rows = [
        {
            "Component": "Statutory Penalties (Expected)",
            "Amount": f"${liability_report['statutory_penalties_expected']:,}",
        },
        {
            "Component": "Class Action Total",
            "Amount": f"${liability_report['class_action_total']:,}",
        },
        {
            "Component": "Attorney Fees",
            "Amount": f"${liability_report['attorney_fees']:,}",
        },
        {
            "Component": "Litigation Costs",
            "Amount": f"${liability_report['litigation_costs']:,}",
        },
        {
            "Component": "Total Expected",
            "Amount": f"${liability_report['total_liability_expected']:,}",
        },
    ]
    st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    breakdown_rows = [
        {
            "Category": item["category"],
            "Violation Type": item["violation_type"],
            "Expected Penalty": f"${item['expected_penalty']:,}",
            "Range": f"${item['min_penalty']:,} - ${item['max_penalty']:,}",
            "Basis": item["basis"],
        }
        for item in liability_report["violation_breakdown"]
    ]
    if breakdown_rows:
        st.subheader("Violation Breakdown")
        st.dataframe(breakdown_rows, use_container_width=True, hide_index=True)

    if liability_report["risk_multipliers"]:
        st.subheader("Risk Multipliers")
        multiplier_rows = [
            {"Factor": key, "Multiplier": value}
            for key, value in liability_report["risk_multipliers"].items()
        ]
        st.dataframe(multiplier_rows, use_container_width=True, hide_index=True)

    if liability_report["warnings"]:
        st.subheader("Warnings")
        for warning in liability_report["warnings"]:
            st.warning(warning)

    return liability_report


def render_benchmark_tab(result: AnalysisResult, result_dict: Dict[str, Any]) -> Dict[str, Any]:
    available_industries = get_available_industries()
    display_names = [display_name for _, display_name in available_industries]

    default_industry = default_benchmark_for_contract(result.contract_type)
    default_display = next(
        (display_name for value, display_name in available_industries if value == default_industry.value),
        display_names[0],
    )

    if not st.session_state.benchmark_industry_name:
        st.session_state.benchmark_industry_name = default_display

    st.session_state.benchmark_industry_name = st.selectbox(
        "Compare against industry benchmark",
        display_names,
        index=display_names.index(st.session_state.benchmark_industry_name)
        if st.session_state.benchmark_industry_name in display_names
        else display_names.index(default_display),
    )

    selected_industry = (
        get_industry_by_name(st.session_state.benchmark_industry_name)
        or default_industry
    )
    comparison = compare_to_industry(result_dict["flagged_clauses"], selected_industry)

    left, right = st.columns([1.4, 1])
    with left:
        benchmark_figure = create_benchmark_radar_chart(
            comparison.user_scores,
            comparison.benchmark_scores,
            comparison.benchmark_name,
            title="Risk Benchmark Comparison",
        )
        st.plotly_chart(benchmark_figure, use_container_width=True)

    with right:
        st.metric("Your Overall Score", f"{comparison.user_overall_score:.1f}/100")
        st.metric("Benchmark Score", f"{comparison.benchmark_overall_score:.1f}/100")
        st.metric("Percentile", f"{comparison.user_percentile}th")
        if comparison.worse_than_benchmark:
            st.error("This contract is more predatory than the selected benchmark.")
        else:
            st.success("This contract is less predatory than the selected benchmark.")

    delta_rows = [
        {
            "Category": category,
            "Your Score": comparison.user_scores[category],
            "Benchmark": comparison.benchmark_scores[category],
            "Delta": comparison.category_deltas[category],
        }
        for category in comparison.user_scores.keys()
    ]
    st.dataframe(delta_rows, use_container_width=True, hide_index=True)

    return normalize_for_storage(comparison)


def build_export_payload(
    result: AnalysisResult,
    liability_report: Dict[str, Any],
    benchmark_report: Dict[str, Any],
) -> Dict[str, Any]:
    payload = normalize_for_storage(result)
    payload["liability_report"] = liability_report
    payload["benchmark_report"] = benchmark_report
    payload["jurisdiction"] = (result.jurisdiction or Jurisdiction.FEDERAL).value
    return payload


def render_sidebar(user_id: str, selected_jurisdiction_name: str) -> tuple[str, str]:
    with st.sidebar:
        st.markdown("## Analysis Controls")

        jurisdiction_names = get_jurisdiction_display_names()
        selected_jurisdiction_name = st.selectbox(
            "Legal Jurisdiction",
            jurisdiction_names,
            index=jurisdiction_names.index(selected_jurisdiction_name)
            if selected_jurisdiction_name in jurisdiction_names
            else 0,
            help="Select the governing legal context before running analysis.",
        )

        selected_jurisdiction = resolve_jurisdiction(selected_jurisdiction_name)
        profile = get_jurisdiction_profile(selected_jurisdiction)
        st.caption(profile.description)

        get_or_create_user(user_id)
        allowed, remaining, tier = check_rate_limit(user_id, "analysis")

        st.markdown("---")
        st.markdown(f"**Plan:** {get_tier_info(tier)['name']}")
        if get_tier_info(tier)["daily_analyses"] == -1:
            st.markdown("**Daily analyses remaining:** Unlimited")
        else:
            st.markdown(f"**Daily analyses remaining:** {remaining}")

        try:
            usage = get_usage_stats(user_id)
        except Exception:
            usage = {}

        if usage:
            st.caption(
                f"Total analyses: {usage.get('total_analyses', 0)} | "
                f"Pages processed: {usage.get('total_pages_processed', 0)}"
            )

        if not allowed:
            st.warning("You have reached your daily analysis limit for this tier.")

        st.markdown("---")
        st.markdown("**Required disclosure checklist**")
        for disclosure in get_required_disclosures(selected_jurisdiction):
            st.write(f"• {disclosure}")

        st.markdown("---")
        st.caption("Privacy: data is processed in-memory for analysis orchestration.")

    return selected_jurisdiction_name, tier


def render_hero() -> None:
    st.markdown(
        """
        <div style='text-align: center; padding: 2rem 0 1rem 0;'>
            <h1 style='font-size: 3rem; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                ⚖️ LEXRISK
            </h1>
            <p style='font-size: 1.15rem; color: #666; margin: 0.5rem 0;'>
                v2.0 Contract Risk Intelligence with jurisdictional rules, liability modeling, and market benchmarks
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.75rem; padding: 2rem 0;'>
            <p><strong>LEXRISK</strong> by Babylon Technologies</p>
            <p>© 2026 Babylon Technologies. Building in public.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


init_session_state()

current_user_id = get_user_id()
stored_jurisdiction_name = st.session_state.get(
    "selected_jurisdiction_name",
    get_jurisdiction_display_names()[0],
)
selected_jurisdiction_name, current_tier = render_sidebar(
    current_user_id,
    stored_jurisdiction_name,
)
st.session_state.selected_jurisdiction_name = selected_jurisdiction_name

render_hero()

st.markdown("### Upload PDF Contract")
uploaded_file = st.file_uploader(
    "Upload a PDF contract",
    type=["pdf"],
    help=f"Maximum file size: {MAX_FILE_SIZE_MB}MB",
)

if uploaded_file:
    try:
        is_valid, error_message = validate_pdf_upload(uploaded_file, current_tier)
        if not is_valid:
            st.error(f"Upload error: {error_message}")
            st.stop()

        with st.spinner("Extracting text from PDF..."):
            extracted_text, extract_error, page_count = extract_pdf_text(uploaded_file, current_tier)

        if extract_error:
            st.error(extract_error)
            st.stop()

        st.session_state.contract_text = extracted_text or ""
        st.session_state.uploaded_page_count = page_count
        st.session_state.uploaded_contract_name = uploaded_file.name
        st.session_state.analysis_complete = False
        st.session_state.last_analysis_result = None
        st.session_state.last_analysis_meta = {}

        st.success(
            f"Extracted {len(st.session_state.contract_text):,} characters from "
            f"{page_count} page(s)."
        )
    except Exception as exc:
        logger.exception("PDF processing error")
        st.error("PDF processing failed. Please try another file.")
        if TELEMETRY_AVAILABLE:
            log_error_telemetry("pdf_processing", str(exc), current_user_id)

st.markdown("---")
contract_text = st.text_area(
    "Or paste contract text",
    value=st.session_state.contract_text,
    height=320,
    placeholder="Paste your agreement, TOS, MSA, DPA, SaaS contract, or employment agreement here...",
)

if contract_text != st.session_state.contract_text:
    st.session_state.contract_text = contract_text
    st.session_state.uploaded_page_count = 0
    st.session_state.analysis_complete = False
    st.session_state.last_analysis_result = None
    st.session_state.last_analysis_meta = {}

st.markdown("---")
agreed = st.checkbox(
    "I understand LexRisk is an AI tool and not a substitute for professional legal advice."
)

analysis_controls = st.columns([1, 1.4, 2.2])
with analysis_controls[0]:
    analyze_clicked = st.button(
        "Analyze Contract",
        type="primary",
        use_container_width=True,
        disabled=not agreed,
    )
with analysis_controls[1]:
    st.caption(f"Jurisdiction: {selected_jurisdiction_name}")
with analysis_controls[2]:
    st.caption("The selected jurisdiction is part of the scoring and cache key.")

if analyze_clicked:
    if not st.session_state.contract_text.strip():
        st.warning("Please upload a PDF or paste contract text before running analysis.")
    else:
        try:
            allowed, remaining, tier = check_rate_limit(current_user_id, "analysis")
            get_or_create_user(current_user_id)

            if not allowed:
                st.error("Daily analysis limit reached for your current tier.")
                st.stop()

            selected_jurisdiction = resolve_jurisdiction(selected_jurisdiction_name)
            contract_hash = get_contract_cache_key(
                st.session_state.contract_text,
                selected_jurisdiction,
            )

            cached_payload = get_cached_analysis(contract_hash)
            was_cached = False

            if cached_payload and cached_payload.get("analysis_result"):
                analysis_result = hydrate_analysis_result(cached_payload["analysis_result"])
                analysis_meta = {
                    "provider_used": cached_payload.get("engine_used", analysis_result.engine_used),
                    "breaker_state": "cache",
                    "failover": False,
                    "processing_time_ms": 0,
                    "was_cached": True,
                }
                was_cached = True
            else:
                with st.spinner("Running v2.0 analysis pipeline..."):
                    analysis_result, analysis_meta = analyze_with_circuit_breaker(
                        st.session_state.contract_text,
                        selected_jurisdiction_name,
                    )
                analysis_meta["was_cached"] = False

                cache_analysis(
                    contract_hash,
                    len(st.session_state.contract_text),
                    analysis_result.risk_score,
                    analysis_result.risk_level,
                    normalize_for_storage(analysis_result),
                    analysis_result.engine_used,
                )

            page_count = (
                st.session_state.uploaded_page_count
                or estimate_manual_page_count(st.session_state.contract_text)
            )

            if not was_cached:
                increment_usage(
                    current_user_id,
                    "analysis",
                    pages=page_count,
                    text_chars=len(st.session_state.contract_text),
                )

            log_analysis(
                current_user_id,
                contract_hash,
                len(st.session_state.contract_text),
                page_count,
                analysis_result.risk_score,
                analysis_result.risk_level,
                analysis_result.engine_used,
                was_cached,
                analysis_meta.get("processing_time_ms", 0),
            )

            for clause in analysis_result.flagged_clauses:
                track_redlined_clause(
                    clause.category,
                    clause.severity,
                    clause.clause_text,
                    contract_hash,
                )

            if TELEMETRY_AVAILABLE:
                log_analysis_telemetry(
                    user_id=current_user_id,
                    contract_length=len(st.session_state.contract_text),
                    risk_score=analysis_result.risk_score,
                    risk_level=analysis_result.risk_level,
                    engine_used=analysis_meta.get("provider_used", analysis_result.engine_used),
                    was_cached=was_cached,
                    processing_time_ms=analysis_meta.get("processing_time_ms", 0),
                    contract_type=analysis_result.contract_type,
                    breaker_state=analysis_meta.get("breaker_state", "n/a"),
                    was_failover=analysis_meta.get("failover", False),
                )

            st.session_state.last_analysis_result = analysis_result
            st.session_state.last_analysis_meta = analysis_meta
            st.session_state.analysis_complete = True
            st.success(
                "Cached result loaded."
                if was_cached
                else "Analysis complete. Tabs below are now populated with v2.0 outputs."
            )
        except CircuitBreakerOpen as exc:
            st.error("OpenAI circuit breaker is open. Please retry shortly or use the Groq path.")
            if TELEMETRY_AVAILABLE:
                log_error_telemetry("circuit_breaker_open", str(exc), current_user_id)
        except Exception as exc:
            logger.exception("Analysis execution failed")
            st.error("Analysis failed. Please try again.")
            if TELEMETRY_AVAILABLE:
                log_error_telemetry("analysis_failure", str(exc), current_user_id)

if st.session_state.analysis_complete and st.session_state.last_analysis_result:
    result: AnalysisResult = st.session_state.last_analysis_result
    result_dict = normalize_for_storage(result)

    active_result_jurisdiction = (result.jurisdiction or Jurisdiction.FEDERAL).value
    selected_jurisdiction_value = resolve_jurisdiction(selected_jurisdiction_name).value
    if active_result_jurisdiction != selected_jurisdiction_value:
        st.info(
            "The sidebar jurisdiction has changed since the last run. "
            "Re-analyze the contract to refresh scoring, liability, and benchmark context."
        )

    st.divider()
    summary_tab, redlines_tab, liability_tab, benchmark_tab = st.tabs(
        ["Summary", "Redlines", "Liability", "Benchmark"]
    )

    with summary_tab:
        render_summary_tab(result, result_dict, st.session_state.contract_text)

    with redlines_tab:
        render_redlines_tab(result_dict, st.session_state.contract_text)

    with liability_tab:
        liability_report = render_liability_tab(result, result_dict)

    with benchmark_tab:
        benchmark_report = render_benchmark_tab(result, result_dict)

    export_payload = build_export_payload(result, liability_report, benchmark_report)

    st.divider()
    st.subheader("Action Layer")
    try:
        pdf_bytes = bootstrap_pdf_generator().generate_report(
            export_payload,
            contract_name=st.session_state.uploaded_contract_name,
            include_liability=True,
        )
        st.download_button(
            "Download Litigation Shield PDF",
            data=pdf_bytes,
            file_name=f"{os.path.splitext(st.session_state.uploaded_contract_name)[0]}_litigation_shield.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as exc:
        logger.exception("PDF export failed")
        st.warning(f"PDF export is currently unavailable: {exc}")

st.divider()
st.caption("Privacy: Data is analyzed in memory and routed through the configured backend services.")
st.caption("Legal: LexRisk is an AI tool and does not provide legal advice or create an attorney-client relationship.")
render_footer()
