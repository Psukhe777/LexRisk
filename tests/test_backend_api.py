"""
tests/test_backend_api.py — Session 1 FastAPI bootstrap tests.

The analysis engine and database are stubbed: these tests assert the HTTP
contract (routes, status codes, response shape, quota behaviour), not LLM output.
"""

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
pytest.importorskip("httpx", reason="httpx not installed")

from fastapi.testclient import TestClient  # noqa: E402

from analyzer import AnalysisResult, FlaggedClause  # noqa: E402
from backend import analysis_service  # noqa: E402
from backend.main import create_app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def fake_result():
    return AnalysisResult(
        risk_score=82,
        risk_level="HIGH",
        flagged_clauses=[
            FlaggedClause(
                clause_text="binding arbitration",
                category="Arbitration",
                severity="HIGH",
                plain_english="You cannot sue.",
                red_flag="Class action waiver.",
            )
        ],
        summary="Aggressive terms.",
        recommendation="NEGOTIATE",
        raw_response="{}",
        disclaimer="Not legal advice.",
        engine_used="groq",
        contract_type="saas",
    )


@pytest.fixture
def stub_pipeline(monkeypatch, fake_result):
    """Stub every DB call and the analyzer; record quota increments."""
    calls = {"increment": [], "logged": [], "cached": None}

    monkeypatch.setattr(analysis_service, "get_or_create_user", lambda *a, **k: True)
    monkeypatch.setattr(analysis_service, "check_rate_limit", lambda *a, **k: (True, 2, "free"))
    monkeypatch.setattr(analysis_service, "get_cached_analysis", lambda h: calls["cached"])
    monkeypatch.setattr(analysis_service, "cache_analysis", lambda *a, **k: True)
    monkeypatch.setattr(
        analysis_service, "increment_usage",
        lambda user_id, *a, **k: calls["increment"].append(user_id) or True,
    )
    monkeypatch.setattr(
        analysis_service, "log_analysis",
        lambda *a, **k: calls["logged"].append(a) or True,
    )
    monkeypatch.setattr(analysis_service, "track_redlined_clause", lambda *a, **k: True)

    class _FakeAnalyzer:
        jurisdiction = None

        def analyze(self, text, force_engine=None, skip_nlp_filter=False):
            return fake_result

    monkeypatch.setattr(analysis_service, "get_analyzer", lambda: _FakeAnalyzer())
    return calls


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "environment", "database", "llm_configured"}


def test_openapi_exposes_the_v1_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/analyze" in paths
    assert "/api/v1/usage" in paths


# ── Analyze ───────────────────────────────────────────────────────────────────

def test_analyze_returns_full_contract(client, stub_pipeline):
    response = client.post(
        "/api/v1/analyze",
        json={"text": "A contract with binding arbitration.", "jurisdiction": "federal"},
        headers={"X-User-Id": "user-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_score"] == 82
    assert body["risk_level"] == "HIGH"
    assert body["flagged_clauses"][0]["category"] == "Arbitration"
    assert body["meta"]["cache_hit"] is False
    assert body["meta"]["engine_used"] == "groq"
    assert body["meta"]["text_truncated"] is False


def test_analyze_rejects_empty_text(client, stub_pipeline):
    response = client.post("/api/v1/analyze", json={"text": ""})
    assert response.status_code == 422  # pydantic min_length


def test_analyze_rejects_unknown_engine(client, stub_pipeline):
    response = client.post("/api/v1/analyze", json={"text": "hi", "force_engine": "gemini"})
    assert response.status_code == 422


def test_analyze_returns_429_when_quota_exhausted(client, stub_pipeline, monkeypatch):
    monkeypatch.setattr(analysis_service, "check_rate_limit", lambda *a, **k: (False, 0, "free"))
    response = client.post("/api/v1/analyze", json={"text": "some contract text"})
    assert response.status_code == 429


def test_cache_hit_still_consumes_quota(client, stub_pipeline, fake_result):
    """Audit FIX 5 enforced at the API layer."""
    stub_pipeline["cached"] = {
        "analysis_result": analysis_service.result_to_payload(fake_result),
        "engine_used": "groq",
    }

    response = client.post(
        "/api/v1/analyze",
        json={"text": "some contract text"},
        headers={"X-User-Id": "replayer"},
    )

    assert response.status_code == 200
    assert response.json()["meta"]["cache_hit"] is True
    assert stub_pipeline["increment"] == ["replayer"], "cache hit must still decrement quota"


def test_unknown_jurisdiction_falls_back_to_federal():
    from jurisdictional_rules import Jurisdiction

    assert analysis_service.resolve_jurisdiction("atlantis") == Jurisdiction.FEDERAL
    assert analysis_service.resolve_jurisdiction(None) == Jurisdiction.FEDERAL


# ── Usage ─────────────────────────────────────────────────────────────────────

def test_usage_endpoint(client, monkeypatch):
    import backend.routers.analysis as analysis_router

    monkeypatch.setattr(analysis_router, "check_rate_limit", lambda *a, **k: (True, 3, "free"))
    response = client.get("/api/v1/usage", headers={"X-User-Id": "u1"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "u1", "tier": "free", "allowed": True, "remaining": 3}


def test_backend_never_imports_streamlit():
    from pathlib import Path

    for path in Path(__file__).resolve().parents[1].joinpath("backend").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import streamlit" not in source, f"{path.name} must stay UI-agnostic"
        assert "st.secrets" not in source, f"{path.name} must not read Streamlit secrets"
