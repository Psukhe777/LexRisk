"""
tests/test_analyzer.py
Pytest test suite for CLAUSE — covers unit tests (no API key needed)
and integration tests (requires GROQ_API_KEY in .env).
Run: pytest tests/ -v
Run unit only: pytest tests/ -v -m "not integration"
Run all: pytest tests/ -v -m "integration" (requires API key)
"""

import json
import os
import sys
from groq import Groq
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import AnalysisResult, ClauseAnalyzer, FlaggedClause
from tests.fixtures.sample_tos import (
    CLEAN_TOS,
    EMPTY_TOS,
    PREDATORY_TOS,
    SHORT_TOS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_predatory_response():
    """Realistic Groq JSON response for a high-risk contract."""
    return json.dumps({
        "risk_score": 87,
        "risk_level": "HIGH",
        "flagged_clauses": [
            {
                "clause_text": "automatically renew at the end of each billing period at the then-current rate",
                "category": "Auto-Renewal",
                "severity": "HIGH",
                "plain_english": "They'll keep charging you automatically and can change the price with only 3 days notice.",
                "red_flag": "60-day written cancellation window is designed to trap you."
            },
            {
                "clause_text": "YOU AGREE THAT ANY DISPUTE ARISING OUT OF OR RELATED TO THESE TERMS...WILL BE RESOLVED BY BINDING ARBITRATION",
                "category": "Arbitration",
                "severity": "HIGH",
                "plain_english": "You give up your right to sue them in court or join a class action lawsuit.",
                "red_flag": "The arbitrator is chosen by the company — not neutral."
            },
            {
                "clause_text": "perpetual, irrevocable, worldwide, royalty-free license to use...any content you submit",
                "category": "Data Rights",
                "severity": "CRITICAL",
                "plain_english": "They own unlimited rights to everything you post, forever, for any purpose including selling it.",
                "red_flag": "Irrevocable means you can never take this permission back."
            }
        ],
        "summary": "This contract contains multiple highly predatory clauses designed to benefit the company at significant expense to the user. The combination of auto-renewal traps, forced arbitration, and broad data rights makes this agreement particularly dangerous.",
        "recommendation": "AVOID"
    })


@pytest.fixture
def mock_clean_response():
    """Groq JSON response for a fair contract."""
    return json.dumps({
        "risk_score": 12,
        "risk_level": "LOW",
        "flagged_clauses": [],
        "summary": "This contract is written in plain English and contains fair, user-friendly terms. No predatory clauses detected.",
        "recommendation": "SIGN"
    })


@pytest.fixture
def analyzer_no_key(monkeypatch):
    """Analyzer instance bypassing API key requirement for unit tests."""
    monkeypatch.setenv("GROQ_API_KEY", "test_key_unit_tests_only")
    return ClauseAnalyzer()


# ── Unit Tests: Initialization ─────────────────────────────────────────────────

class TestClauseAnalyzerInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GROQ_API_KEY not set"):
            ClauseAnalyzer()

    def test_accepts_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test_key_abc123")
        analyzer = ClauseAnalyzer()
        assert analyzer.api_key == "test_key_abc123"

    def test_accepts_key_directly(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        analyzer = ClauseAnalyzer(api_key="direct_key_xyz")
        assert analyzer.api_key == "direct_key_xyz"

    def test_default_model(self, analyzer_no_key):
        assert analyzer_no_key.model == "llama3-70b-8192"

    def test_temperature_is_float(self, analyzer_no_key):
        assert isinstance(analyzer_no_key.temperature, float)
        assert 0.0 <= analyzer_no_key.temperature <= 1.0


# ── Unit Tests: Input Validation ──────────────────────────────────────────────

class TestInputValidation:
    def test_raises_on_empty_text(self, analyzer_no_key):
        with pytest.raises(ValueError, match="cannot be empty"):
            analyzer_no_key.analyze(EMPTY_TOS)

    def test_raises_on_whitespace_only(self, analyzer_no_key):
        with pytest.raises(ValueError, match="cannot be empty"):
            analyzer_no_key.analyze("   \n\t  ")


# ── Unit Tests: Response Parsing ──────────────────────────────────────────────

class TestResponseParsing:
    def test_parses_predatory_response(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_response(mock_predatory_response)

        assert isinstance(result, AnalysisResult)
        assert result.risk_score == 87
        assert result.risk_level == "HIGH"
        assert result.recommendation == "AVOID"
        assert len(result.flagged_clauses) == 3

    def test_parses_clean_response(self, analyzer_no_key, mock_clean_response):
        result = analyzer_no_key._parse_response(mock_clean_response)

        assert result.risk_score == 12
        assert result.risk_level == "LOW"
        assert result.recommendation == "SIGN"
        assert len(result.flagged_clauses) == 0

    def test_parses_flagged_clause_fields(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_response(mock_predatory_response)
        clause = result.flagged_clauses[0]

        assert isinstance(clause, FlaggedClause)
        assert clause.category == "Auto-Renewal"
        assert clause.severity == "HIGH"
        assert len(clause.plain_english) > 0
        assert len(clause.red_flag) > 0

    def test_strips_markdown_fences(self, analyzer_no_key):
        """Model sometimes wraps JSON in ```json ... ``` fences."""
        wrapped = f"```json\n{json.dumps({'risk_score': 5, 'risk_level': 'LOW', 'flagged_clauses': [], 'summary': 'OK', 'recommendation': 'SIGN'})}\n```"
        result = analyzer_no_key._parse_response(wrapped)
        assert result.risk_score == 5

    def test_raises_on_invalid_json(self, analyzer_no_key):
        with pytest.raises(ValueError, match="invalid JSON"):
            analyzer_no_key._parse_response("this is not json at all")

    def test_risk_score_is_int(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_response(mock_predatory_response)
        assert isinstance(result.risk_score, int)

    def test_raw_response_preserved(self, analyzer_no_key, mock_predatory_response):
        result = analyzer_no_key._parse_response(mock_predatory_response)
        assert result.raw_response == mock_predatory_response


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
# These only run if GROQ_API_KEY is set in your .env
# Run with: pytest tests/ -v -m integration

@pytest.mark.integration
class TestGroqIntegration:
    @pytest.fixture
    def real_analyzer(self):
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("GROQ_API_KEY")
        if not key or key.startswith("your_"):
            pytest.skip("GROQ_API_KEY not configured — add to .env to run integration tests")
        return ClauseAnalyzer()

    def test_predatory_tos_gets_high_risk(self, real_analyzer):
        result = real_analyzer.analyze(PREDATORY_TOS)

        assert isinstance(result, AnalysisResult)
        assert result.risk_score >= 50, f"Expected high risk score, got {result.risk_score}"
        assert result.risk_level in ("MEDIUM", "HIGH", "CRITICAL")
        assert len(result.flagged_clauses) >= 1
        assert result.recommendation in ("NEGOTIATE", "AVOID")

    def test_clean_tos_gets_low_risk(self, real_analyzer):
        result = real_analyzer.analyze(CLEAN_TOS)

        assert isinstance(result, AnalysisResult)
        assert result.risk_score <= 40, f"Expected low risk score, got {result.risk_score}"
        assert result.recommendation in ("SIGN", "NEGOTIATE")

    def test_result_has_all_fields(self, real_analyzer):
        result = real_analyzer.analyze(SHORT_TOS)

        assert hasattr(result, "risk_score")
        assert hasattr(result, "risk_level")
        assert hasattr(result, "flagged_clauses")
        assert hasattr(result, "summary")
        assert hasattr(result, "recommendation")
        assert hasattr(result, "raw_response")

    def test_risk_score_in_valid_range(self, real_analyzer):
        result = real_analyzer.analyze(PREDATORY_TOS)
        assert 0 <= result.risk_score <= 100

    def test_flagged_clauses_have_required_fields(self, real_analyzer):
        result = real_analyzer.analyze(PREDATORY_TOS)
        for clause in result.flagged_clauses:
            assert clause.clause_text
            assert clause.category
            assert clause.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert clause.plain_english

