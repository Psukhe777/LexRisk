"""
tests/test_analyzer.py
Pytest test suite for LexRisk's ClauseAnalyzer — unit tests (no API key needed)
and integration tests (require a real GROQ_API_KEY).

Run:            pytest tests/ -v
Unit only:      pytest tests/ -v -m "not integration"
Integration:    pytest tests/ -v -m integration

NOTE: this suite was rewritten to target the CURRENT analyzer surface
(`_parse_and_enforce_matrix`, deterministic scoring matrix, dual Groq/OpenAI
engines). The previous version still asserted a long-removed API
(`_parse_response`, `analyzer.model`, `analyzer.temperature`) and could not
even be imported.
"""

import json

import pytest

from analyzer import (
    AnalysisError,
    AnalysisResult,
    ClauseAnalyzer,
    FlaggedClause,
)
from tests.fixtures.sample_tos import (
    CLEAN_TOS,
    EMPTY_TOS,
    PREDATORY_TOS,
    SHORT_TOS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_predatory_response():
    """Realistic LLM JSON response for a high-risk contract."""
    return json.dumps({
        "score": 87,
        "lvl": "HIGH",
        "flags": [
            {
                "txt": "automatically renew at the end of each billing period at the then-current rate",
                "cat": "Auto-Renewal",
                "sev": "HIGH",
                "desc": "They'll keep charging you automatically and can change the price with only 3 days notice.",
                "red": "60-day written cancellation window is designed to trap you.",
            },
            {
                "txt": "ANY DISPUTE ARISING OUT OF THESE TERMS WILL BE RESOLVED BY BINDING ARBITRATION",
                "cat": "Arbitration",
                "sev": "HIGH",
                "desc": "You give up your right to sue them in court or join a class action lawsuit.",
                "red": "The arbitrator is chosen by the company — not neutral.",
            },
            {
                "txt": "perpetual, irrevocable, worldwide, royalty-free license to any content you submit",
                "cat": "IP Rights",
                "sev": "CRITICAL",
                "desc": "They own unlimited rights to everything you post, forever, including selling it.",
                "red": "Irrevocable means you can never take this permission back.",
            },
        ],
        "sum": "This contract contains multiple highly predatory clauses: auto-renewal traps, forced arbitration and broad IP rights.",
        "rec": "AVOID",
    })


@pytest.fixture
def mock_clean_response():
    """LLM JSON response for a fair contract."""
    return json.dumps({
        "score": 12,
        "lvl": "LOW",
        "flags": [],
        "sum": "Fair, user-friendly terms. No predatory clauses detected.",
        "rec": "SIGN",
    })


@pytest.fixture
def analyzer_no_key(monkeypatch):
    """Analyzer wired to a dummy key, NLP pre-filter disabled (no model download)."""
    monkeypatch.setenv("GROQ_API_KEY", "test_key_unit_tests_only")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return ClauseAnalyzer(enable_nlp_filter=False)


# ── Unit Tests: Initialization ─────────────────────────────────────────────────

class TestClauseAnalyzerInit:
    def test_raises_without_any_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="At least one API key"):
            ClauseAnalyzer(enable_nlp_filter=False)

    def test_accepts_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test_key_abc123")
        analyzer = ClauseAnalyzer(enable_nlp_filter=False)
        assert analyzer.groq_key == "test_key_abc123"

    def test_accepts_key_directly(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        analyzer = ClauseAnalyzer(api_key="direct_key_xyz", enable_nlp_filter=False)
        assert analyzer.groq_key == "direct_key_xyz"

    def test_keys_come_from_environment_only(self, monkeypatch):
        """Regression guard: no Streamlit secrets fallback (audit FIX 1)."""
        monkeypatch.setenv("GROQ_API_KEY", "env_key")
        analyzer = ClauseAnalyzer(enable_nlp_filter=False)
        assert analyzer.groq_key == "env_key"
        assert analyzer.groq_client is not None

    def test_nlp_filter_can_be_disabled(self, analyzer_no_key):
        assert analyzer_no_key.enable_nlp_filter is False
        assert analyzer_no_key.nlp_engine is None


# ── Unit Tests: Input Validation ──────────────────────────────────────────────

class TestInputValidation:
    def test_raises_on_empty_text(self, analyzer_no_key):
        with pytest.raises(ValueError, match="cannot be empty"):
            analyzer_no_key.analyze(EMPTY_TOS)

    def test_raises_on_whitespace_only(self, analyzer_no_key):
        with pytest.raises(ValueError, match="cannot be empty"):
            analyzer_no_key.analyze("   \n\t  ")


# ── Unit Tests: Response Parsing & Scoring Matrix ─────────────────────────────

class TestResponseParsing:
    def test_parses_predatory_response(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_and_enforce_matrix(mock_predatory_response, "consumer")

        assert isinstance(result, AnalysisResult)
        assert result.risk_level in ("HIGH", "CRITICAL")
        assert result.risk_score >= 70
        assert result.recommendation == "AVOID"
        assert len(result.flagged_clauses) == 3

    def test_parses_clean_response(self, analyzer_no_key, mock_clean_response):
        result = analyzer_no_key._parse_and_enforce_matrix(mock_clean_response, "saas")

        assert result.risk_level == "LOW"
        assert result.risk_score < 40
        assert result.recommendation == "SIGN"
        assert result.flagged_clauses == []

    def test_parses_flagged_clause_fields(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_and_enforce_matrix(mock_predatory_response, "consumer")
        clause = result.flagged_clauses[0]

        assert isinstance(clause, FlaggedClause)
        assert clause.category == "Auto-Renewal"
        assert clause.severity == "HIGH"
        assert clause.plain_english
        assert clause.red_flag

    def test_strips_markdown_fences(self, analyzer_no_key):
        """The model sometimes wraps JSON in ```json ... ``` fences."""
        payload = {"score": 5, "lvl": "LOW", "flags": [], "sum": "OK", "rec": "SIGN"}
        wrapped = f"```json\n{json.dumps(payload)}\n```"
        result = analyzer_no_key._parse_and_enforce_matrix(wrapped, "saas")
        assert result.risk_level == "LOW"

    def test_raises_analysis_error_on_invalid_json(self, analyzer_no_key):
        with pytest.raises(AnalysisError, match="unparseable JSON"):
            analyzer_no_key._parse_and_enforce_matrix("this is not json at all", "saas")

    def test_risk_score_is_int_in_range(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_and_enforce_matrix(mock_predatory_response, "consumer")
        assert isinstance(result.risk_score, int)
        assert 0 <= result.risk_score <= 100

    def test_raw_response_preserved(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_and_enforce_matrix(mock_predatory_response, "consumer")
        assert result.raw_response == mock_predatory_response

    def test_disclaimer_always_present(self, analyzer_no_key, mock_clean_response):
        result = analyzer_no_key._parse_and_enforce_matrix(mock_clean_response, "saas")
        assert "not a legal professional" in result.disclaimer


# ── Unit Tests: Contract Type Detection ───────────────────────────────────────

class TestContractTypeDetection:
    def test_detects_a_type_for_predatory_fixture(self):
        from analyzer import ContractTypeDetector

        info = ContractTypeDetector.detect(PREDATORY_TOS)
        assert set(info) == {"type", "confidence", "indicators"}
        assert 0.0 <= info["confidence"] <= 1.0

    def test_unknown_type_for_trivial_text(self):
        from analyzer import ContractTypeDetector

        assert ContractTypeDetector.detect("hello world")["type"] == "unknown"


# ── Unit Tests: Sample TOS Fixtures ───────────────────────────────────────────

class TestSampleFixtures:
    def test_predatory_tos_has_content(self):
        assert len(PREDATORY_TOS) > 500
        assert "ARBITRATION" in PREDATORY_TOS
        assert "automatically renew" in PREDATORY_TOS.lower()

    def test_clean_tos_has_content(self):
        assert len(CLEAN_TOS) > 100

    def test_empty_tos_is_empty(self):
        assert EMPTY_TOS == ""

    def test_short_tos_is_short(self):
        assert len(SHORT_TOS) < 100


# ── Integration Tests: Real Groq API ──────────────────────────────────────────
# Only run with: pytest tests/ -v -m integration   (needs a real GROQ_API_KEY)

@pytest.mark.integration
class TestGroqIntegration:
    @pytest.fixture
    def real_analyzer(self):
        import os

        from dotenv import load_dotenv

        load_dotenv()
        key = os.getenv("GROQ_API_KEY")
        if not key or key.startswith("your_") or key.startswith("test_"):
            pytest.skip("GROQ_API_KEY not configured — set it to run integration tests")
        return ClauseAnalyzer(provider="groq", enable_nlp_filter=False)

    def test_predatory_tos_gets_high_risk(self, real_analyzer):
        result = real_analyzer.analyze(PREDATORY_TOS)
        assert isinstance(result, AnalysisResult)
        assert result.risk_score >= 50, f"Expected high risk score, got {result.risk_score}"
        assert result.risk_level in ("MEDIUM", "HIGH", "CRITICAL")
        assert len(result.flagged_clauses) >= 1
        assert result.recommendation in ("NEGOTIATE", "AVOID")

    def test_clean_tos_gets_low_risk(self, real_analyzer):
        result = real_analyzer.analyze(CLEAN_TOS)
        assert result.risk_score <= 40, f"Expected low risk score, got {result.risk_score}"
        assert result.recommendation in ("SIGN", "NEGOTIATE")

    def test_result_has_all_fields(self, real_analyzer):
        result = real_analyzer.analyze(SHORT_TOS)
        for field in (
            "risk_score", "risk_level", "flagged_clauses", "summary",
            "recommendation", "raw_response", "text_truncated", "truncated_at_chars",
        ):
            assert hasattr(result, field)

    def test_flagged_clauses_have_required_fields(self, real_analyzer):
        result = real_analyzer.analyze(PREDATORY_TOS)
        for clause in result.flagged_clauses:
            assert clause.clause_text
            assert clause.category
            assert clause.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert clause.plain_english
