import logging
import os
import sys
import time
import hashlib
import pdfplumber
import streamlit as st
from dotenv import load_dotenv
import plotly.graph_objects as go
 
# ── 1. Page Config (MUST BE FIRST STREAMLIT COMMAND) ──────────────────────────
st.set_page_config(
    page_title="Lexrisk ⚖️",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="expanded",
)
 
# ── 2. Local Imports & Config ─────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
 # TEMPORARY DEBUGGING

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
 
# Import new modules with DETAILED error handling
try:
    from analyzer import ClauseAnalyzer
    ANALYZER_AVAILABLE = True
    logger.info("✅ analyzer.py loaded successfully")
except SyntaxError as e:
    logger.error(f"❌ SYNTAX ERROR in analyzer.py at line {e.lineno}: {e.msg}")
    ANALYZER_AVAILABLE = False
    st.error(f"""
    **SYNTAX ERROR in analyzer.py**
    
    Line {e.lineno}: {e.msg}
    
    Please check your analyzer.py file for:
    - Missing quotes or brackets
    - Incorrect indentation
    - Invalid Python syntax
    
    Error details: {e.text}
    """)
    st.stop()
except ImportError as e:
    logger.error(f"❌ IMPORT ERROR: {e}")
    ANALYZER_AVAILABLE = False
    st.error(f"""
    **Cannot import analyzer.py**
    
    Error: {e}
    
    Possible causes:
    1. File is missing from repository
    2. File has a dependency error
    3. Required package is missing
    
    Check that analyzer.py exists and all packages in requirements.txt are installed.
    """)
    st.stop()
except Exception as e:
    logger.error(f"❌ UNKNOWN ERROR loading analyzer.py: {e}")
    import traceback
    ANALYZER_AVAILABLE = False
    st.error(f"""
    **Error loading analyzer.py**
    
    {e}
    
    Full traceback:
    """)
    st.code(traceback.format_exc())
    st.stop()
 
try:
    from demo_data import DEMOS  
    DEMOS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"demo_data.py not found: {e}")
    DEMOS = {}
    DEMOS_AVAILABLE = False
 
try:
    from rate_limiter_v2 import (
        get_user_id, 
        check_rate_limit, 
        increment_usage,
        initialize_rate_limiter,
        format_usage_display,
        get_tier_info,
        TIER_LIMITS
    )
    RATE_LIMITER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"rate_limiter_v2.py not found: {e}")
    RATE_LIMITER_AVAILABLE = False
    def get_user_id():
        return ("anonymous", "free")
    def check_rate_limit(user_id, action):
        return (True, 999, None, "free")
    def increment_usage(user_id, action, pages=1, text_chars=0):
        pass
    def initialize_rate_limiter():
        pass
    def format_usage_display(user_id):
        return ""
    def get_tier_info(tier):
        return {'name': 'Free', 'max_pages': 10, 'max_text_chars': 50000, 'daily_analyses': 5}
    TIER_LIMITS = {'free': {'daily_analyses': 5}}
 
try:
    from redliner import get_redlined_html, get_redlining_summary
    REDLINER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"redliner.py not found: {e}")
    REDLINER_AVAILABLE = False
    def get_redlined_html(text, clauses):
        return "<p>Redlining feature not available</p>"
    def get_redlining_summary(clauses):
        return "<p>Summary not available</p>"
 
try:
    from db_utils import (
        get_contract_hash,
        get_cached_analysis,
        cache_analysis,
        log_analysis,
        track_redlined_clause
    )
    DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"db_utils.py not found: {e}")
    DB_AVAILABLE = False
 
if RATE_LIMITER_AVAILABLE:
    initialize_rate_limiter()
 
if 'contract_text' not in st.session_state:
    st.session_state.contract_text = ""
if 'demo_active' not in st.session_state:
    st.session_state.demo_active = False
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'last_analysis_result' not in st.session_state:
    st.session_state.last_analysis_result = None
if 'show_redlined_view' not in st.session_state:
    st.session_state.show_redlined_view = False
 
st.markdown("""
<style>
    header {visibility: hidden !important;}
    [data-testid="stHeader"] {visibility: hidden !important;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    [data-testid="viewerBadge"] {display: none !important;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
 
    .risk-critical { color: #ff4444; font-weight: bold; font-size: 1.5rem; }
    .risk-high     { color: #ff8800; font-weight: bold; font-size: 1.5rem; }
    .risk-medium   { color: #ffcc00; font-weight: bold; font-size: 1.5rem; }
    .risk-low      { color: #44cc44; font-weight: bold; font-size: 1.5rem; }
    
    .cache-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        margin: 0.5rem 0;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
</style>
""", unsafe_allow_html=True)
 
@st.cache_data(ttl=3600, show_spinner=False)
def analyze_contract_cached(contract_text: str, provider: str = "groq") -> dict:
    if not ANALYZER_AVAILABLE:
        raise ValueError("Analyzer module not available")
    
    logger.info(f"🔄 Cache MISS - Running new analysis for contract ({len(contract_text)} chars)")
    
    # ✅ FIXED: OpenAI instead of Gemini
    if provider == "openai":
        api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    else:
        api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    
    if not api_key:
        raise ValueError(f"Missing API key for {provider}")
    
    analyzer = ClauseAnalyzer(api_key=api_key, provider=provider)
    result = analyzer.analyze(contract_text)
    
    result_dict = {
        'risk_score': result.risk_score,
        'risk_level': result.risk_level,
        'summary': result.summary,
        'recommendation': result.recommendation,
        'disclaimer': result.disclaimer,
        'engine_used': result.engine_used,
        'contract_type': result.contract_type,
        'flagged_clauses': [
            {
                'category': c.category,
                'severity': c.severity,
                'clause_text': c.clause_text,
                'plain_english': c.plain_english,
                'red_flag': c.red_flag
            }
            for c in result.flagged_clauses
        ]
    }
    
    return result_dict
 
def create_risk_gauge(score):
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
 
def show_analysis_progress():
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
        time.sleep(0.5)
    
    status_text.empty()
    progress_bar.empty()
 
st.markdown("""
<div style='text-align: center; padding: 2rem 0 1rem 0;'>
    <h1 style='font-size: 3rem; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
        ⚖️ LEXRISK
    </h1>
    <p style='font-size: 1.2rem; color: #666; margin: 0.5rem 0;'>
        AI-Powered Predatory Clause Scanner
    </p>
</div>
""", unsafe_allow_html=True)
 
with st.sidebar:
    st.markdown("## 🎯 Quick Start")
    user_id, user_type = get_user_id()
    usage_html = format_usage_display(user_id)
    if usage_html:
        st.markdown(usage_html, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if DEMOS_AVAILABLE and DEMOS:
        st.markdown("### 📚 Try a Demo Contract")
        demo_options = ["None"] + list(DEMOS.keys())
        selected_demo = st.selectbox("Select a demo:", demo_options)
        
        if selected_demo != "None" and selected_demo in DEMOS:
            if st.button("Load Demo", use_container_width=True):
                st.session_state.contract_text = DEMOS[selected_demo]['text']
                st.session_state.demo_active = True
                st.session_state.analysis_complete = False
                st.rerun()
    
    st.markdown("---")
    st.markdown("### 🚀 Upgrade")
    st.markdown("Need more scans or unlimited pages?")
    
    if st.button("View Pro Plans →", use_container_width=True):
        st.info("Upgrade feature coming soon!")
    
    st.markdown("---")
    st.caption("🔒 Privacy: Data analyzed in memory, immediately discarded")
 
st.markdown("### 📄 Upload PDF Contract")
 
uploaded_file = st.file_uploader(
    "Upload a PDF contract (or paste text below)",
    type=['pdf'],
    help="Upload any contract, Terms of Service, or legal agreement as a PDF"
)
 
if uploaded_file:
    try:
        user_id, _ = get_user_id()
        allowed, remaining, _, tier = check_rate_limit(user_id, "analysis")
        tier_info = get_tier_info(tier)
        max_pages = tier_info['max_pages']
        
        with pdfplumber.open(uploaded_file) as pdf:
            page_count = len(pdf.pages)
            
            if max_pages != -1 and page_count > max_pages:
                st.error(f"""
                🚫 **Page Limit Exceeded**
                
                Your {tier_info['name']} plan allows {max_pages} pages, but this PDF has {page_count} pages.
                """)
                st.stop()
            
            text_parts = []
            for page in pdf.pages[:max_pages if max_pages != -1 else None]:
                text_parts.append(page.extract_text() or "")
            
            extracted_text = "\n\n".join(text_parts)
            
            max_chars = tier_info['max_text_chars']
            if max_chars != -1 and len(extracted_text) > max_chars:
                extracted_text = extracted_text[:max_chars]
                st.warning(f"⚠️ Text truncated to {max_chars:,} characters")
            
            st.session_state.contract_text = extracted_text
            st.session_state.demo_active = False
            st.session_state.analysis_complete = False
            
            st.success(f"✅ Extracted {len(extracted_text):,} characters from {page_count} page(s)")
            
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
 
st.markdown("---")
 
contract_text = st.text_area(
    "Or paste your contract text here",
    value=st.session_state.contract_text,
    height=300,
    placeholder="Paste any TOS, contract, or legal agreement...",
)
 
if contract_text != st.session_state.contract_text:
    st.session_state.contract_text = contract_text
    st.session_state.demo_active = False
    st.session_state.analysis_complete = False
 
st.markdown("---")
 
agreed = st.checkbox(
    "I understand Lexrisk is an AI tool and not a substitute for professional legal advice."
)
 
col1, col2, col3 = st.columns([1, 1, 2])
 
with col1:
    analyze_btn = st.button(
        "🔍 Analyze", 
        type="primary", 
        use_container_width=True, 
        disabled=not agreed
    )
 
with col2:
    if st.session_state.analysis_complete and st.session_state.last_analysis_result:
        toggle_view = st.button(
            "🎨 Toggle View",
            use_container_width=True,
            help="Switch between summary and redlined contract view"
        )
        if toggle_view:
            st.session_state.show_redlined_view = not st.session_state.show_redlined_view
            st.rerun()
 
if not agreed:
    st.info("💡 Please check the box above to enable the analysis.")
 
if analyze_btn and st.session_state.contract_text.strip():
    start_time = time.time()
    was_cached = False
    
    try:
        user_id, user_type = get_user_id()
        allowed, remaining, reset_time, tier = check_rate_limit(user_id, "analysis")
        
        if not allowed and RATE_LIMITER_AVAILABLE:
            st.error(f"🛑 **Daily Scan Limit Reached**")
            st.stop()
        
        if st.session_state.demo_active and DEMOS_AVAILABLE:
            show_analysis_progress()
            
            demo_match = next((d['analysis'] for d in DEMOS.values() 
                             if d['text'] == st.session_state.contract_text), None)
            
            if demo_match:
                result_dict = demo_match
                was_cached = True
                st.success("⚡ Demo Loaded (No API Call)")
            else:
                st.session_state.demo_active = False
        
        contract_hash = None
        if not st.session_state.demo_active and DB_AVAILABLE:
            contract_hash = get_contract_hash(st.session_state.contract_text)
            cached_result = get_cached_analysis(contract_hash)
            
            if cached_result:
                result_dict = cached_result['analysis_result']
                was_cached = True
                st.markdown('<p class="cache-badge">⚡ INSTANT: Cached Result</p>', 
                          unsafe_allow_html=True)
        
        if not was_cached and not st.session_state.demo_active:
            show_analysis_progress()
            
            # ✅ FIXED: OpenAI for long contracts
            text_length = len(st.session_state.contract_text)
            provider = "openai" if text_length > 4500 else "groq"
            
            result_dict = analyze_contract_cached(st.session_state.contract_text, provider)
            
            if DB_AVAILABLE and contract_hash:
                cache_analysis(
                    contract_hash,
                    text_length,
                    result_dict['risk_score'],
                    result_dict['risk_level'],
                    result_dict,
                    result_dict['engine_used']
                )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        if not was_cached and RATE_LIMITER_AVAILABLE:
            page_count = st.session_state.contract_text.count('\n\n') // 50 + 1
            increment_usage(user_id, "analysis", pages=page_count, 
                          text_chars=len(st.session_state.contract_text))
        
        if DB_AVAILABLE and contract_hash:
            page_count = st.session_state.contract_text.count('\n\n') // 50 + 1
            log_analysis(
                user_id,
                contract_hash,
                len(st.session_state.contract_text),
                page_count,
                result_dict['risk_score'],
                result_dict['risk_level'],
                result_dict['engine_used'],
                was_cached,
                processing_time_ms
            )
            
            for clause in result_dict['flagged_clauses']:
                track_redlined_clause(
                    clause['category'],
                    clause['severity'],
                    clause['clause_text'],
                    contract_hash
                )
        
        st.session_state.last_analysis_result = result_dict
        st.session_state.analysis_complete = True
        st.rerun()
        
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        logger.error(f"Analysis error: {traceback.format_exc()}")
 
if st.session_state.analysis_complete and st.session_state.last_analysis_result:
    result = st.session_state.last_analysis_result
    
    st.divider()
    
    if not st.session_state.show_redlined_view:
        st.markdown("## 📊 Analysis Results")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            gauge_fig = create_risk_gauge(result['risk_score'])
            st.plotly_chart(gauge_fig, use_container_width=True)
        
        with col2:
            st.markdown("### Key Metrics")
            risk_class = f"risk-{result['risk_level'].lower()}"
            st.markdown(f'<p class="{risk_class}">{result["risk_level"]}</p>', 
                       unsafe_allow_html=True)
            
            st.metric("Risk Score", f"{result['risk_score']}/100")
            st.metric("Flagged Clauses", len(result['flagged_clauses']))
            
            rec_emoji = {"SIGN": "✅", "NEGOTIATE": "⚠️", "AVOID": "🚫"}.get(
                result['recommendation'], "❓")
            st.metric("Recommendation", f"{rec_emoji} {result['recommendation']}")
        
        st.progress(result['risk_score'] / 100)
        
        st.markdown("### 📝 Executive Summary")
        st.info(result['summary'])
        
        if result['flagged_clauses']:
            st.divider()
            st.markdown(f"### 🚨 {len(result['flagged_clauses'])} Flagged Clause(s)")
            
            for i, clause in enumerate(result['flagged_clauses'], 1):
                severity_color = {
                    'LOW': '🟢',
                    'MEDIUM': '🟡', 
                    'HIGH': '🟠',
                    'CRITICAL': '🔴'
                }.get(clause['severity'], '⚪')
                
                with st.expander(f"{severity_color} {i}. {clause['category']} — {clause['severity']}"):
                    st.markdown("**📋 Clause Text:**")
                    st.code(clause['clause_text'], language=None)
                    st.markdown(f"**💬 Plain English:** {clause['plain_english']}")
                    st.markdown(f"**⚠️ Red Flag:** {clause['red_flag']}")
        else:
            st.success("✅ No predatory clauses detected!")
        
        legal_text = result.get('disclaimer', "This analysis is for informational purposes only.")
        st.warning(f"⚖️ **Legal Notice:** {legal_text}")
        
    else:
        st.markdown("## 🎨 Redlined Contract View")
        summary_html = get_redlining_summary(result['flagged_clauses'])
        st.markdown(summary_html, unsafe_allow_html=True)
        st.divider()
        redlined_html = get_redlined_html(
            st.session_state.contract_text,
            result['flagged_clauses']
        )
        st.markdown(redlined_html, unsafe_allow_html=True)
 
st.divider()
st.caption("🔒 **Privacy:** Data is analyzed in memory and immediately discarded.")
st.caption("⚖️ **Legal:** Lexrisk is an AI tool, not a law firm. No legal advice provided.")
 
st.markdown('''
<div style='text-align: center; color: #666; font-size: 0.75rem; padding: 2rem 0;'>
    <p><strong>LEXRISK</strong> by Babylon Technologies</p>
    <p>© 2026 Babylon Technologies. Building in public.</p>
</div>
''', unsafe_allow_html=True)
