"""
tests/test_preflight_fixes.py — Regression tests for the Session 0.5 pre-migration fixes.

One test per audit fix. Each test fails against the pre-fix code.
Heavy third-party deps (streamlit, sentence-transformers, groq/openai SDKs) are
stubbed so these tests run in a bare CI container.
"""

import json
import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY STUBS
# ══════════════════════════════════════════════════════════════════════════════

def _stub(name: str, **attrs):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _install_stubs():
    _stub("dotenv", load_dotenv=lambda *a, **k: None)
    _stub("groq", Groq=lambda *a, **k: None)
    _stub("openai", OpenAI=lambda *a, **k: None)

    class _ST:
        def __init__(self, *a, **k):
            pass

        def encode(self, texts, **k):
            return [[0.0] for _ in texts]

    _stub("sentence_transformers", SentenceTransformer=_ST)

    try:
        import psycopg2  # noqa: F401
    except ImportError:
        pg = _stub("psycopg2", connect=lambda *a, **k: None)
        pool = _stub("psycopg2.pool", ThreadedConnectionPool=object)
        extras = _stub("psycopg2.extras", RealDictCursor=object)
        pg.pool = pool
        pg.extras = extras

    if "sklearn" not in sys.modules:
        sklearn = _stub("sklearn")
        metrics = _stub("sklearn.metrics")
        pairwise = _stub("sklearn.metrics.pairwise", cosine_similarity=lambda a, b: [])
        sklearn.metrics = metrics
        metrics.pairwise = pairwise


_install_stubs()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def read_source(filename: str) -> str:
    return (REPO_ROOT / filename).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1 — analyzer.py: no st.secrets coupling, JSON guard, truncation flags
# ══════════════════════════════════════════════════════════════════════════════

def test_fix1_analyzer_has_no_streamlit_coupling():
    src = read_source("analyzer.py")
    assert "st.secrets" not in src, "analyzer.py must not read Streamlit secrets"
    assert "import streamlit" not in src, "analyzer.py must not import streamlit"
    assert not re.search(r"^\s*except:\s*$", src, re.MULTILINE), "no bare except allowed"
    assert 'os.getenv("GROQ_API_KEY")' in src
    assert 'os.getenv("OPENAI_API_KEY")' in src


def test_fix1_unparseable_llm_json_raises_analysis_error():
    import analyzer

    inst = object.__new__(analyzer.ClauseAnalyzer)
    inst.jurisdiction = None

    with pytest.raises(analyzer.AnalysisError) as exc:
        inst._parse_and_enforce_matrix("not json at all {", "saas")
    assert "unparseable JSON" in str(exc.value)

    # sanity: valid JSON still parses
    ok = inst._parse_and_enforce_matrix(json.dumps({"score": 10, "flags": []}), "saas")
    assert ok.risk_level == "LOW"


def test_fix1_truncation_is_reported_on_result():
    import analyzer

    short_text, truncated, at = analyzer.ClauseAnalyzer.truncate_for_llm("x" * 100)
    assert (truncated, at) == (False, None)
    assert len(short_text) == 100

    long_text, truncated, at = analyzer.ClauseAnalyzer.truncate_for_llm("x" * (analyzer.MAX_LLM_CHARS + 1))
    assert truncated is True
    assert at == analyzer.MAX_LLM_CHARS
    assert len(long_text) == analyzer.MAX_LLM_CHARS

    result = analyzer.AnalysisResult(
        risk_score=0, risk_level="LOW", flagged_clauses=[], summary="",
        recommendation="SIGN", raw_response="{}", disclaimer="",
    )
    assert result.text_truncated is False
    assert result.truncated_at_chars is None


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2 — nlp_engine.py: document order + middle-of-document fallback
# ══════════════════════════════════════════════════════════════════════════════

def _fake_engine(similarities):
    """Build an NLPVectorizationEngine with a deterministic fake similarity matrix."""
    import nlp_engine

    eng = object.__new__(nlp_engine.NLPVectorizationEngine)
    eng.similarity_threshold = 0.65
    eng.chunk_size = 1
    eng.max_chunks_to_send = 50
    eng.clause_texts = ["pattern"]
    eng.clause_metadata = [{"category": "Arbitration", "severity": "HIGH"}]
    eng.clause_embeddings = [[0.0]]

    class _Model:
        def encode(self, texts, **k):
            return [[0.0] for _ in texts]

    eng.model = _Model()
    nlp_engine.cosine_similarity = lambda a, b: [[s] for s in similarities]
    nlp_engine.np = types.SimpleNamespace(argmax=lambda row: 0)
    return eng


def test_fix2_high_risk_chunks_preserve_document_order():
    text = " ".join(f"Sentence number {i} of the contract." for i in range(5))
    # ascending similarity => reverse order if sorted by score alone
    eng = _fake_engine([0.70, 0.75, 0.80, 0.85, 0.90])

    result = eng.filter_high_risk_chunks(text)

    indices = [m.chunk_index for m in result.matched_clauses]
    assert indices == sorted(indices), f"chunks must be in document order, got {indices}"
    assert result.high_risk_chunks == [m.chunk_text for m in result.matched_clauses]
    # the highest-similarity chunk is NOT first — order is positional, not by score
    assert result.matched_clauses[0].similarity_score == pytest.approx(0.70)


def test_fix2_zero_match_fallback_comes_from_document_middle():
    text = " ".join(f"Sentence number {i} of the contract." for i in range(30))
    eng = _fake_engine([0.1] * 30)

    result = eng.filter_high_risk_chunks(text)

    assert result.chunks_flagged == 0
    assert len(result.high_risk_chunks) == 10
    assert "number 0 " not in result.high_risk_chunks[0], "must not fall back to the title page"
    assert "number 10 " in result.high_risk_chunks[0]


# ══════════════════════════════════════════════════════════════════════════════
# FIX 3 — db_utils.py: redlined_clauses dedupe
# ══════════════════════════════════════════════════════════════════════════════

def test_fix3_redlined_clauses_have_unique_index_and_upsert():
    src = read_source("db_utils.py")

    assert "uq_redlined_clause" in src, "unique index migration missing"
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_redlined_clause" in src
    assert "GENERATED ALWAYS AS (encode(sha256(clause_text::bytea), 'hex')) STORED" in src

    insert = src[src.index("INSERT INTO redlined_clauses"):]
    insert = insert[:insert.index('"""')]
    assert "ON CONFLICT DO NOTHING" not in insert, "DO NOTHING never fired — must upsert"
    assert "detection_count = redlined_clauses.detection_count + 1" in insert


# ══════════════════════════════════════════════════════════════════════════════
# FIX 4 — schema.sql idempotency + full table verification
# ══════════════════════════════════════════════════════════════════════════════

def test_fix4_every_index_is_idempotent():
    src = read_source("schema.sql")
    offenders = [
        line.strip() for line in src.splitlines()
        if line.strip().upper().startswith("CREATE INDEX")
        and "IF NOT EXISTS" not in line.upper()
    ]
    assert offenders == [], f"non-idempotent index statements: {offenders}"


def test_fix4_schema_gate_checks_every_table_not_just_users():
    import db_utils

    assert hasattr(db_utils, "REQUIRED_TABLES")
    for table in (
        "schema_version", "users", "usage_limits", "analysis_cache",
        "analysis_history", "tier_limits", "redlined_clauses",
    ):
        assert table in db_utils.REQUIRED_TABLES

    assert isinstance(db_utils.SCHEMA_VERSION, int)
    assert "CREATE TABLE IF NOT EXISTS schema_version" in read_source("schema.sql")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 5 — main.py: cache hits still consume quota
# ══════════════════════════════════════════════════════════════════════════════

def test_fix5_cache_hit_does_not_bypass_quota():
    src = read_source("main.py")

    assert "if not was_cached:\n                increment_usage(" not in src, \
        "cache hits must not skip increment_usage()"
    assert not re.search(r"if not was_cached:\s*\n\s*increment_usage\(", src)
    assert "increment_usage(" in src
    assert "cache_hit BOOLEAN" in read_source("schema.sql"), \
        "analysis_history needs a cache_hit column to track the ratio"
    assert "cache_hit" in read_source("db_utils.py")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 6 — telemetry.py documented as broken
# ══════════════════════════════════════════════════════════════════════════════

def test_fix6_telemetry_is_marked_broken():
    head = read_source("telemetry.py")[:600]
    assert "BROKEN SINCE CREATION" in head
    assert "Do not use this module" in head
    assert "audit finding 5.1" in head


# ══════════════════════════════════════════════════════════════════════════════
# FIX 7 — conflicting tier limit dicts quarantined
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("filename", ["main.py", "rate_limiter.py"])
def test_fix7_python_tier_limits_are_quarantined(filename):
    src = read_source(filename)
    idx = src.index("TIER_LIMITS = {")
    preamble = src[max(0, idx - 400):idx]
    assert "CONFLICT" in preamble, f"{filename} TIER_LIMITS lacks the conflict warning"
    assert "Single source of truth: tier_limits table" in preamble
    assert "audit finding 5.3" in preamble
