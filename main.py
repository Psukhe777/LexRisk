"""
main.py — CLAUSE: AI-powered predatory clause scanner
Run: streamlit run main.py
"""

import logging
import os
import sys

import  streamlit as st
from dotenv import load_dotenv
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("Missing GROQ_API_KEY. Please add it to Streamlit Secrets or your .env file.")
    st.stop()
    
sys.path.insert(0, os.path.dirname(__file__))
from analyzer import ClauseAnalyzer

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CLAUSE ⚖️",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Styles ────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .risk-critical { color: #ff4444; font-weight: bold; font-size: 1.5rem; }
    .risk-high     { color: #ff8800; font-weight: bold; font-size: 1.5rem; }
    .risk-medium   { color: #ffcc00; font-weight: bold; font-size: 1.5rem; }
    .risk-low      { color: #44cc44; font-weight: bold; font-size: 1.5rem; }
    .clause-card   { background: #1a1a2e; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("⚖️ CLAUSE")
st.caption("AI Safety Gauge for Predatory Legal Contracts — *Building in public, Day 1*")
st.divider()

# ── Input ─────────────────────────────────────────────────────────────────────

contract_text = st.text_area(
    "Paste your contract or Terms of Service here",
    height=300,
    placeholder="Paste any TOS, contract, or legal agreement...",
)

col1, col2 = st.columns([1, 3])
with col1:
    analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)

# ── Analysis ──────────────────────────────────────────────────────────────────

if analyze_btn and contract_text.strip():
    try:
        analyzer = ClauseAnalyzer()

        with st.spinner("CLAUSE is scanning for predatory language..."):
            result = analyzer.analyze(contract_text)

        # Risk Score
        st.divider()
        risk_class = f"risk-{result.risk_level.lower()}"
        st.markdown(f"### Overall Risk Score")
        st.markdown(
            f'<p class="{risk_class}">{result.risk_score}/100 — {result.risk_level}</p>',
            unsafe_allow_html=True
        )
        st.progress(result.risk_score / 100)

        # Recommendation
        rec_emoji = {"SIGN": "✅", "NEGOTIATE": "⚠️", "AVOID": "🚫"}.get(result.recommendation, "❓")
        st.info(f"{rec_emoji} **Recommendation:** {result.recommendation}")

        # Summary
        st.markdown(f"**Summary:** {result.summary}")

        # Flagged Clauses
        if result.flagged_clauses:
            st.divider()
            st.markdown(f"### 🚨 {len(result.flagged_clauses)} Flagged Clause(s)")
            for i, clause in enumerate(result.flagged_clauses, 1):
                with st.expander(f"{i}. {clause.category} — {clause.severity}"):
                    st.markdown(f"**Clause Text:**")
                    st.code(clause.clause_text, language=None)
                    st.markdown(f"**Plain English:** {clause.plain_english}")
                    st.markdown(f"**⚠️ Red Flag:** {clause.red_flag}")
        else:
            st.success("✅ No predatory clauses detected.")

    except ValueError as e:
        st.error(f"Configuration error: {e}")
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        st.caption("Make sure your GROQ_API_KEY is set in .env")

elif analyze_btn:
    st.warning("Please paste some contract text first.")
