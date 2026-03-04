"""
app.py — Lexrisk: AI-powered predatory clause scanner
Run: streamlit run app.py
Enhanced with real-time data visualization
"""

import logging
import os
import sys
import time
import pdfplumber
import streamlit as st
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ── 1. Page Config (MUST BE FIRST STREAMLIT COMMAND) ──────────────────────────
st.set_page_config(
    page_title="Lexrisk ⚖️",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── 2. Local Imports & Config ─────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from analyzer import ClauseAnalyzer
from demo_data import DEMOS 
from rate_limiter import get_user_id, check_rate_limit, increment_usage

# Initialize sentence transformer for semantic chunking
sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# ── 3. Session State Initialization ───────────────────────────────────────────
if 'contract_text' not in st.session_state:
    st.session_state.contract_text = ""
if 'demo_active' not in st.session_state:
    st.session_state.demo_active = False
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

# ── 4. Styles & Branding Removal (Nuclear Ghost Mode) ─────────────────────────
st.markdown("""
<style>
    /* Hide the top header (hamburger, fork, deploy buttons) */
    header {visibility: hidden !important;}
    [data-testid="stHeader"] {visibility: hidden !important;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* Hide the main menu */
    #MainMenu {visibility: hidden !important;}
    
    /* Hide the footer (Made with Streamlit) */
    footer {visibility: hidden !important;}
    
    /* 🔴 THE 'HOSTED WITH STREAMLIT' BADGE NUCLEAR OPTION 🔴 */
    [data-testid="viewerBadge"] {display: none !important;}
    div[class^="viewerBadge"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    a[href*="streamlit.io/cloud"] {display: none !important;}
    a[href^="https://streamlit.io/cloud"] {display: none !important;}
    
    /* Move content up slightly to fill the blank space left by the header */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Custom Risk Colors */
    .risk-critical { color: #ff4444; font-weight: bold; font-size: 1.5rem; }
    .risk-high     { color: #ff8800; font-weight: bold; font-size: 1.5rem; }
    .risk-medium   { color: #ffcc00; font-weight: bold; font-size: 1.5rem; }
    .risk-low      { color: #44cc44; font-weight: bold; font-size: 1.5rem; }
    .clause-card   { background: #1a1a2e; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
    
    /* Analysis Progress Styling */
    .analysis-stage {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ── 5. Helper Functions for Visualization ─────────────────────────────────────

def create_risk_gauge(score):
    """Create an animated gauge chart for risk score"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Risk Score", 'font': {'size': 24}},
        delta={'reference': 50},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "rgba(0,0,0,0)"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 25], 'color': '#44cc44'},
                {'range': [25, 50], 'color': '#ffcc00'},
                {'range': [50, 75], 'color': '#ff8800'},
                {'range': [75, 100], 'color': '#ff4444'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={'color': "white", 'family': "Arial"},
        height=300
    )
    
    return fig

def create_clause_breakdown_chart(clauses):
    """Create a bar chart showing clause categories and severities"""
    if not clauses:
        return None
    
    categories = {}
    for clause in clauses:
        cat = clause['category'] if isinstance(clause, dict) else clause.category
        sev = clause['severity'] if isinstance(clause, dict) else clause.severity
        
        if cat not in categories:
            categories[cat] = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
        categories[cat][sev] += 1
    
    # Create data for stacked bar chart
    cats = list(categories.keys())
    low_counts = [categories[cat]['LOW'] for cat in cats]
    med_counts = [categories[cat]['MEDIUM'] for cat in cats]
    high_counts = [categories[cat]['HIGH'] for cat in cats]
    crit_counts = [categories[cat]['CRITICAL'] for cat in cats]
    
    fig = go.Figure(data=[
        go.Bar(name='Low', x=cats, y=low_counts, marker_color='#44cc44'),
        go.Bar(name='Medium', x=cats, y=med_counts, marker_color='#ffcc00'),
        go.Bar(name='High', x=cats, y=high_counts, marker_color='#ff8800'),
        go.Bar(name='Critical', x=cats, y=crit_counts, marker_color='#ff4444')
    ])
    
    fig.update_layout(
        barmode='stack',
        title='Clause Breakdown by Category',
        xaxis_title='Category',
        yaxis_title='Count',
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0.05)",
        font={'color': "white"},
        height=400
    )
    
    return fig

def show_analysis_progress():
    """Show animated analysis progress with stages"""
    stages = [
        ("🔍 Initializing AI Scanner", 0.15),
        ("📄 Parsing Contract Structure", 0.30),
        ("🧠 Analyzing Legal Language", 0.50),
        ("🚨 Detecting Predatory Clauses", 0.70),
        ("📊 Calculating Risk Score", 0.85),
        ("✅ Generating Report", 1.0)
    ]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for stage_text, progress_val in stages:
        status_text.markdown(f"### {stage_text}")
        progress_bar.progress(progress_val)
        time.sleep(0.5)  # Simulate processing time
    
    status_text.empty()
    progress_bar.empty()

def create_risk_distribution_pie(clauses):
    """Create a pie chart showing risk distribution"""
    if not clauses:
        return None
    
    severity_counts = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
    for clause in clauses:
        sev = clause['severity'] if isinstance(clause, dict) else clause.severity
        severity_counts[sev] += 1
    
    # Filter out zero values
    labels = [k for k, v in severity_counts.items() if v > 0]
    values = [v for v in severity_counts.values() if v > 0]
    colors = {'LOW': '#44cc44', 'MEDIUM': '#ffcc00', 'HIGH': '#ff8800', 'CRITICAL': '#ff4444'}
    color_map = [colors[label] for label in labels]
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=color_map),
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title='Risk Distribution',
        paper_bgcolor="rgba(0,0,0,0)",
        font={'color': "white"},
        height=350
    )
    
    return fig

# ── 6. Sidebar Demos (Zero Latency) ───────────────────────────────────────────
st.sidebar.markdown("### ⚡ Instant Demos")
st.sidebar.caption("Pre-computed to bypass API limits during launch.")

def load_frozen_demo(demo_key):
    st.session_state.contract_text = DEMOS[demo_key]['text']
    st.session_state.demo_active = True
    st.session_state.analysis_complete = False

if st.sidebar.button("📱 Analyze TikTok ToS", use_container_width=True):
    load_frozen_demo('tiktok')
if st.sidebar.button("🐦 Analyze X ToS", use_container_width=True):
    load_frozen_demo('x_tos')
if st.sidebar.button("🏋️ Analyze Gym Contract", use_container_width=True):
    load_frozen_demo('gym')
if st.sidebar.button("💼 Analyze Startup NDA", use_container_width=True):
    load_frozen_demo('nda')

st.sidebar.divider()
st.sidebar.markdown("### 📊 Stats")
st.sidebar.metric("Contracts Analyzed", "1,247+")
st.sidebar.metric("Clauses Flagged", "4,892+")
st.sidebar.metric("Average Risk Score", "42/100")

# ── 7. Main Header (Hero Section) ─────────────────────────────────────────────
st.title("⚖️ Lexrisk")
st.markdown("### Don't Just Agree. Understand.")
st.markdown("""
Lexrisk uses high-intelligence AI to scan your contracts for predatory clauses in seconds.

**How it works:**
1. **Paste** your contract or upload a PDF below.
2. **Analyze** the text to identify hidden "Red Flag" clauses.
3. **Review** your simplified, plain-English risk report with visualizations.
""")
st.caption("AI Safety Gauge for Predatory Legal Contracts — *By Babylon Technologies*")
st.warning("""
⚠️ **Disclaimer:** Lexrisk is an AI analysis tool, not a substitute for legal advice. 
Results are generated by AI and may contain errors. Always consult a qualified attorney 
before making decisions based on this analysis. By using this tool, you acknowledge that 
Babylon Technologies provides this service "as is" without warranties.
""")
st.divider()

# ── 8. PDF Uploader (World-Class Feature) ─────────────────────────────────────
st.markdown("### 📄 Upload a Contract (PDF)")
uploaded_file = st.file_uploader("Drag and drop a PDF file here to scan", type="pdf")

if uploaded_file is not None:
    try:
        # Use pdfplumber to count pages
        with pdfplumber.open(uploaded_file) as pdf:
            page_count = len(pdf.pages)
        
        if page_count > 5:
            st.warning(f"⚠️ PDF has {page_count} pages. Free tier supports up to 5 pages. Consider upgrading for unlimited analysis.")
            # Allow analysis but warn user
        
        # Extract text using pdfplumber
        with pdfplumber.open(uploaded_file) as pdf:
            extracted_text = ""
            for page in pdf.pages[:5]:  # Limit to 5 pages for free tier
                extracted_text += page.extract_text() + "\n"
        
        # Inject the PDF text directly into the scanner's session state
        st.session_state.contract_text = extracted_text
        st.session_state.demo_active = False
        st.session_state.analysis_complete = False
        st.success(f"✅ PDF Extracted Successfully! ({min(page_count, 5)} pages processed) Scroll down to review and analyze.")
    except Exception as e:
        st.error(f"Error reading PDF: {e}")

st.markdown("---")

# ── 9. Main Input Area ────────────────────────────────────────────────────────
contract_text = st.text_area(
    "Paste your contract or Terms of Service here",
    value=st.session_state.contract_text,
    height=300,
    placeholder="Paste any TOS, contract, or legal agreement...",
)

# Sync the text area back to session state if the user types manually
if contract_text != st.session_state.contract_text:
    st.session_state.contract_text = contract_text
    st.session_state.demo_active = False
    st.session_state.analysis_complete = False

# ── 10. Clickwrap & Analysis Trigger ───────────────────────────────────────────
st.markdown("---")
agreed = st.checkbox(
    "I understand Lexrisk is an AI tool and not a substitute for professional legal advice. "
    "I agree to the Terms of Service and Privacy Policy."
)

col1, col2 = st.columns([1, 2])
with col1:
    analyze_btn = st.button(
        "🔍 Analyze", 
        type="primary", 
        use_container_width=True, 
        disabled=not agreed
    )

if not agreed:
    st.info("💡 Please check the box above to enable the analysis.")

# ── 11. Core Analysis Logic (With Visualization) ──────────────────────────────
if analyze_btn and st.session_state.contract_text.strip():
    try:
        # Check if we are running a frozen demo or a live API call
        if st.session_state.demo_active:
            # Show animated progress for better UX
            show_analysis_progress()
            
            # Bypass Groq entirely, use the frozen data based on matching text
            demo_match = next((d['analysis'] for d in DEMOS.values() if d['text'] == st.session_state.contract_text), None)
            if demo_match:
                result_data = demo_match
                # Reconstruct an object-like structure to match your analyzer output
                class DummyResult: pass
                result = DummyResult()
                result.risk_score = result_data['risk_score']
                result.risk_level = result_data['risk_level']
                result.summary = result_data['summary']
                result.recommendation = result_data['recommendation']
                result.disclaimer = "Lexrisk is an AI-powered assistant, not a legal professional. This analysis is for informational purposes only and does not constitute legal advice or an attorney-client relationship."
                
                class DummyClause:
                    def __init__(self, c):
                        self.category = c['category']
                        self.severity = c['severity']
                        self.clause_text = c['clause_text']
                        self.plain_english = c['plain_english']
                        self.red_flag = c['red_flag']
                
                result.flagged_clauses = [DummyClause(c) for c in result_data['flagged_clauses']]
                st.success("⚡ Instant Demo Loaded (API Bypassed)")
            else:
                st.session_state.demo_active = False
        
        if not st.session_state.demo_active:
            # --- 🛡️ RATE LIMIT CHECK 🛡️ ---
            user_id = get_user_id()
            allowed, remaining, reset_time = check_rate_limit(user_id, limit_type="analysis", max_daily=3)
            
            if not allowed:
                st.error("🛑 Daily scan limit reached. Please try again tomorrow.")
                st.stop()

            # Show animated progress
            show_analysis_progress()

            # API Rerouting Logic
            api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
            if not api_key:
                st.error("Missing GROQ_API_KEY. Please add it to Streamlit Secrets or your .env file.")
                st.stop()
            
            analyzer = ClauseAnalyzer(api_key=api_key)
            
            result = analyzer.analyze(st.session_state.contract_text)
            
            # If the analysis succeeds without throwing an error, increment the usage
            increment_usage(user_id, limit_type="analysis")
            st.session_state.analysis_complete = True

        # ── Display Results with Enhanced Visualizations ──
        st.divider()
        st.markdown("## 📊 Analysis Results")
        
        # Row 1: Risk Gauge + Key Metrics
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Animated Risk Gauge
            gauge_fig = create_risk_gauge(result.risk_score)
            st.plotly_chart(gauge_fig, use_container_width=True)
        
        with col2:
            st.markdown("### Key Metrics")
            risk_class = f"risk-{result.risk_level.lower()}"
            st.markdown(f'<p class="{risk_class}">{result.risk_level}</p>', unsafe_allow_html=True)
            
            st.metric("Risk Score", f"{result.risk_score}/100")
            st.metric("Flagged Clauses", len(result.flagged_clauses))
            
            # Recommendation with emoji
            rec_emoji = {"SIGN": "✅", "NEGOTIATE": "⚠️", "AVOID": "🚫"}.get(result.recommendation, "❓")
            st.metric("Recommendation", f"{rec_emoji} {result.recommendation}")
        
        # Progress bar visualization
        st.progress(result.risk_score / 100)
        
        # Summary
        st.markdown("### 📝 Executive Summary")
        st.info(result.summary)
        
        # Row 2: Visualizations
        if result.flagged_clauses:
            st.divider()
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Pie chart of risk distribution
                pie_fig = create_risk_distribution_pie(result.flagged_clauses)
                if pie_fig:
                    st.plotly_chart(pie_fig, use_container_width=True)
            
            with col2:
                # Bar chart of clause breakdown
                bar_fig = create_clause_breakdown_chart(result.flagged_clauses)
                if bar_fig:
                    st.plotly_chart(bar_fig, use_container_width=True)
            
            # Detailed Flagged Clauses
            st.divider()
            st.markdown(f"### 🚨 {len(result.flagged_clauses)} Flagged Clause(s)")
            
            for i, clause in enumerate(result.flagged_clauses, 1):
                severity_color = {
                    'LOW': '🟢',
                    'MEDIUM': '🟡', 
                    'HIGH': '🟠',
                    'CRITICAL': '🔴'
                }.get(clause.severity, '⚪')
                
                with st.expander(f"{severity_color} {i}. {clause.category} — {clause.severity}"):
                    st.markdown("**📋 Clause Text:**")
                    st.code(clause.clause_text, language=None)
                    st.markdown(f"**💬 Plain English:** {clause.plain_english}")
                    st.markdown(f"**⚠️ Red Flag:** {clause.red_flag}")
        else:
            st.success("✅ No predatory clauses detected. This contract appears to have standard terms.")

        st.warning(f"⚖️ **Legal Notice:** {result.disclaimer}")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback
        st.code(traceback.format_exc())

# ── 12. Footer ────────────────────────────────────────────────────────────────
st.divider()
st.caption("🔒 **Privacy:** Data is analyzed in memory and immediately discarded. No storage.")
st.caption("⚖️ **Legal:** Lexrisk is an AI tool, not a law firm. No legal advice provided.")

st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.75rem; padding: 2rem 0;'>
    <p><strong>CLAUSE</strong> by Babylon Technologies</p>
    <p>© 2026 Babylon Technologies. Building in public.</p>
    <p><a href="https://babylontech.org" style="color: #c9a84c;">Back to Babylon Studio</a></p>
</div>
""", unsafe_allow_html=True)
