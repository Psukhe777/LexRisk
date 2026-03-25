"""
app.py — LexRisk Main Application (Production Hardened)
Features:
- Graceful error handling with branded UI fallbacks
- Circuit breaker integration for API resilience
- Strict upload limits and validation
- Memory-efficient PDF processing
- Real-time telemetry logging
"""

import logging
import os
import sys
import time
import hashlib
import pdfplumber
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, Dict, Any

# ── 1. Page Config (MUST BE FIRST STREAMLIT COMMAND) ──────────────────────────
st.set_page_config(
    page_title="Lexrisk ⚖️",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── 2. Local Imports & Configuration ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# ── 3. Strict Upload Limits ────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 25  # 25MB hard limit
MAX_PDF_PAGES_FREE = 50  # Free tier max
MAX_PDF_PAGES_PRO = 500  # Pro tier max
MAX_TEXT_CHARS_FREE = 100000  # ~100KB text
MAX_TEXT_CHARS_PRO = 1000000  # ~1MB text

# ── 4. Import Modules with Error Handling ──────────────────────────────────────
try:
    from circuit_breaker import get_openai_circuit_breaker, CircuitBreakerOpen
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    logger.warning("circuit_breaker.py not found - degraded mode")
    CIRCUIT_BREAKER_AVAILABLE = False

try:
    from analyzer import ClauseAnalyzer
    ANALYZER_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to load analyzer: {e}")
    ANALYZER_AVAILABLE = False
    st.error("⚠️ **System Initialization Error** - Please contact support")
    st.stop()

try:
    from rate_limiter_v2 import (
        get_user_id, check_rate_limit, increment_usage,
        initialize_rate_limiter, format_usage_display, get_tier_info, TIER_LIMITS
    )
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    def get_user_id(): return ("anonymous", "free")
    def check_rate_limit(uid, act): return (True, 999, None, "free")
    def increment_usage(uid, act, p=1, tc=0): pass
    def initialize_rate_limiter(): pass
    def format_usage_display(uid): return ""
    def get_tier_info(t): return {'name': 'Free', 'max_pages': 50, 'max_text_chars': 100000, 'daily_analyses': 5}
    TIER_LIMITS = {'free': {'daily_analyses': 5}}

try:
    from telemetry import log_analysis_telemetry, log_error_telemetry
    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    def log_analysis_telemetry(*args, **kwargs): pass
    def log_error_telemetry(*args, **kwargs): pass

try:
    from views import render_risk_gauge, render_flagged_clauses, render_hero
    VIEWS_AVAILABLE = True
except ImportError:
    VIEWS_AVAILABLE = False
    logger.warning("views.py not found - using fallback UI")

try:
    from db_utils import (
        get_contract_hash, get_cached_analysis, cache_analysis,
        log_analysis, track_redlined_clause
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

try:
    from redliner import get_redlined_html, get_redlining_summary
    REDLINER_AVAILABLE = True
except ImportError:
    REDLINER_AVAILABLE = False
    def get_redlined_html(text, clauses): return "<p>Redlining unavailable</p>"
    def get_redlining_summary(clauses): return "<p>Summary unavailable</p>"

try:
    from demo_data import DEMOS
    DEMOS_AVAILABLE = True
except ImportError:
    DEMOS = {}
    DEMOS_AVAILABLE = False

# ── 5. Initialize Systems ───────────────────────────────────────────────────────
if RATE_LIMITER_AVAILABLE:
    initialize_rate_limiter()

# ── 6. Session State Initialization ────────────────────────────────────────────
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
if 'api_error_count' not in st.session_state:
    st.session_state.api_error_count = 0

# ── 7. CSS Styling ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    header {visibility: hidden !important;}
    [data-testid="stHeader"] {visibility: hidden !important;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    .error-banner {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin: 2rem 0;
        animation: pulse 2s infinite;
    }
    
    .warning-banner {
        background: linear-gradient(135deg, #feca57 0%, #ff9ff3 100%);
        color: #2d3436;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin: 2rem 0;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.85; }
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def validate_pdf_upload(uploaded_file, tier: str) -> tuple[bool, Optional[str]]:
    """
    Validate PDF upload against strict limits.
    Returns: (is_valid, error_message)
    """
    # Check file size
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return False, f"File size ({file_size_mb:.1f}MB) exceeds maximum ({MAX_FILE_SIZE_MB}MB)"
    
    # Check page count
    tier_info = get_tier_info(tier)
    max_pages = tier_info.get('max_pages', MAX_PDF_PAGES_FREE)
    
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            page_count = len(pdf.pages)
            
            if max_pages != -1 and page_count > max_pages:
                return False, (
                    f"PDF has {page_count} pages but your {tier_info['name']} plan "
                    f"allows {max_pages} pages"
                )
    except Exception as e:
        return False, f"Failed to read PDF: {str(e)}"
    
    return True, None


def extract_pdf_text(uploaded_file, tier: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract text from PDF with memory-efficient processing.
    Returns: (extracted_text, error_message)
    """
    try:
        tier_info = get_tier_info(tier)
        max_pages = tier_info.get('max_pages', MAX_PDF_PAGES_FREE)
        max_chars = tier_info.get('max_text_chars', MAX_TEXT_CHARS_FREE)
        
        text_parts = []
        total_chars = 0
        
        with pdfplumber.open(uploaded_file) as pdf:
            pages_to_process = min(len(pdf.pages), max_pages) if max_pages != -1 else len(pdf.pages)
            
            for i, page in enumerate(pdf.pages[:pages_to_process]):
                if max_chars != -1 and total_chars >= max_chars:
                    break
                
                page_text = page.extract_text() or ""
                
                # Truncate if approaching limit
                if max_chars != -1:
                    remaining = max_chars - total_chars
                    page_text = page_text[:remaining]
                
                text_parts.append(page_text)
                total_chars += len(page_text)
            
            extracted_text = "\n\n".join(text_parts)
            
            if max_chars != -1 and len(extracted_text) > max_chars:
                extracted_text = extracted_text[:max_chars]
                logger.warning(f"Text truncated to {max_chars:,} characters")
            
            return extracted_text, None
            
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return None, f"Failed to extract text: {str(e)}"


def analyze_with_circuit_breaker(contract_text: str, user_id: str) -> Dict[str, Any]:
    """
    Analyze contract with circuit breaker protection.
    Automatically fails over to Groq if OpenAI is failing.
    """
    text_length = len(contract_text)
    start_time = time.time()
    
    # Determine initial provider
    initial_provider = "openai" if text_length > 4500 else "groq"
    
    # Try with circuit breaker
    if CIRCUIT_BREAKER_AVAILABLE and initial_provider == "openai":
        breaker = get_openai_circuit_breaker()
        
        try:
            # Wrap OpenAI call in circuit breaker
            def openai_call():
                return analyze_contract_cached(contract_text, "openai")
            
            result = breaker.call(openai_call)
            result['_provider_used'] = 'openai'
            result['_breaker_state'] = breaker.get_state()
            
        except CircuitBreakerOpen as e:
            logger.warning(f"Circuit breaker OPEN - falling back to Groq: {e}")
            
            # Circuit is open - use Groq fallback
            result = analyze_contract_cached(contract_text, "groq")
            result['_provider_used'] = 'groq'
            result['_breaker_state'] = 'open'
            result['_failover'] = True
            
            st.info("⚡ **Fast Mode Active** - Using optimized processing engine")
            
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            
            # OpenAI failed but circuit not yet open - try Groq
            logger.info("Attempting Groq fallback after OpenAI failure")
            result = analyze_contract_cached(contract_text, "groq")
            result['_provider_used'] = 'groq'
            result['_failover'] = True
    else:
        # Use initial provider without circuit breaker
        result = analyze_contract_cached(contract_text, initial_provider)
        result['_provider_used'] = initial_provider
        result['_breaker_state'] = 'n/a'
    
    processing_time = time.time() - start_time
    result['_processing_time'] = processing_time
    
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_contract_cached(contract_text: str, provider: str = "groq") -> dict:
    """Cached analysis function"""
    if not ANALYZER_AVAILABLE:
        raise ValueError("Analyzer module not available")
    
    logger.info(f"🔄 Cache MISS - Running {provider} analysis ({len(contract_text)} chars)")
    
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


# ══════════════════════════════════════════════════════════════════════════════
# MAIN UI FLOW
# ══════════════════════════════════════════════════════════════════════════════

# Hero Section
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

# Sidebar
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
        st.switch_page("pages/signup.py")
    
    st.markdown("---")
    st.caption("🔒 Privacy: Data analyzed in memory, immediately discarded")

# Main Content
st.markdown("### 📄 Upload PDF Contract")

uploaded_file = st.file_uploader(
    "Upload a PDF contract (or paste text below)",
    type=['pdf'],
    help=f"Maximum file size: {MAX_FILE_SIZE_MB}MB"
)

if uploaded_file:
    try:
        user_id, _ = get_user_id()
        _, _, _, tier = check_rate_limit(user_id, "analysis")
        
        # Validate upload
        is_valid, error_msg = validate_pdf_upload(uploaded_file, tier)
        
        if not is_valid:
            st.error(f"🚫 **Upload Error**: {error_msg}")
            
            if "plan allows" in error_msg:
                st.info("💡 **Tip**: Upgrade to Pro for unlimited page processing")
                if st.button("View Pro Plans"):
                    st.switch_page("pages/signup.py")
            
            st.stop()
        
        # Extract text
        with st.spinner("📄 Extracting text from PDF..."):
            extracted_text, extract_error = extract_pdf_text(uploaded_file, tier)
        
        if extract_error:
            st.error(f"❌ {extract_error}")
            st.stop()
        
        st.session_state.contract_text = extracted_text
        st.session_state.demo_active = False
        st.session_state.analysis_complete = False
        
        with pdfplumber.open(uploaded_file) as pdf:
            page_count = len(pdf.pages)
        
        st.success(f"✅ Extracted {len(extracted_text):,} characters from {page_count} page(s)")
        
    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        st.error("❌ **PDF Processing Error** - Please try a different file or contact support")
        
        if TELEMETRY_AVAILABLE:
            log_error_telemetry("pdf_processing", str(e), user_id)

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

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS EXECUTION (WITH GRACEFUL ERROR HANDLING)
# ══════════════════════════════════════════════════════════════════════════════

if analyze_btn and st.session_state.contract_text.strip():
    start_time = time.time()
    was_cached = False
    result_dict = None
    
    try:
        user_id, user_type = get_user_id()
        allowed, remaining, reset_time, tier = check_rate_limit(user_id, "analysis")
        
        # Check rate limit
        if not allowed and RATE_LIMITER_AVAILABLE:
            st.error("🛑 **Daily Scan Limit Reached**")
            st.info("Upgrade to Pro for 50 scans per day")
            st.stop()
        
        # Demo mode handling
        if st.session_state.demo_active and DEMOS_AVAILABLE:
            with st.spinner("🔍 Analyzing demo contract..."):
                time.sleep(1)  # Simulate processing
            
            demo_match = next((d['analysis'] for d in DEMOS.values() 
                             if d['text'] == st.session_state.contract_text), None)
            
            if demo_match:
                result_dict = demo_match
                was_cached = True
                st.success("⚡ Demo Loaded (No API Call)")
            else:
                st.session_state.demo_active = False
        
        # Database cache check
        contract_hash = None
        if not st.session_state.demo_active and DB_AVAILABLE:
            contract_hash = get_contract_hash(st.session_state.contract_text)
            cached_result = get_cached_analysis(contract_hash)
            
            if cached_result:
                result_dict = cached_result['analysis_result']
                was_cached = True
                st.success("⚡ **INSTANT**: Cached Result")
        
        # Live analysis with circuit breaker
        if not was_cached and not st.session_state.demo_active:
            with st.spinner("🔍 Analyzing contract with AI..."):
                result_dict = analyze_with_circuit_breaker(
                    st.session_state.contract_text,
                    user_id
                )
            
            # Cache the result
            if DB_AVAILABLE and contract_hash:
                cache_analysis(
                    contract_hash,
                    len(st.session_state.contract_text),
                    result_dict['risk_score'],
                    result_dict['risk_level'],
                    result_dict,
                    result_dict.get('engine_used', 'unknown')
                )
        
        # Calculate metrics
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Increment usage
        if not was_cached and RATE_LIMITER_AVAILABLE:
            page_count = st.session_state.contract_text.count('\n\n') // 50 + 1
            increment_usage(user_id, "analysis", pages=page_count, 
                          text_chars=len(st.session_state.contract_text))
        
        # Log telemetry
        if TELEMETRY_AVAILABLE:
            log_analysis_telemetry(
                user_id=user_id,
                contract_length=len(st.session_state.contract_text),
                risk_score=result_dict['risk_score'],
                risk_level=result_dict['risk_level'],
                engine_used=result_dict.get('_provider_used', result_dict.get('engine_used', 'unknown')),
                was_cached=was_cached,
                processing_time_ms=processing_time_ms,
                contract_type=result_dict.get('contract_type', 'unknown'),
                breaker_state=result_dict.get('_breaker_state', 'n/a'),
                was_failover=result_dict.get('_failover', False)
            )
        
        # Log to database
        if DB_AVAILABLE and contract_hash:
            page_count = st.session_state.contract_text.count('\n\n') // 50 + 1
            log_analysis(
                user_id,
                contract_hash,
                len(st.session_state.contract_text),
                page_count,
                result_dict['risk_score'],
                result_dict['risk_level'],
                result_dict.get('engine_used', 'unknown'),
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
        
        # Store result and trigger rerun
        st.session_state.last_analysis_result = result_dict
        st.session_state.analysis_complete = True
        st.session_state.api_error_count = 0  # Reset error counter on success
        st.rerun()
        
    except CircuitBreakerOpen as e:
        # Circuit breaker is open - show maintenance message
        logger.error(f"Circuit breaker prevented request: {e}")
        
        st.markdown("""
        <div class="warning-banner">
            <h3 style="margin: 0;">⚠️ System Maintenance</h3>
            <p style="margin: 0.5rem 0;">
                LexRisk is currently processing an unusually high volume of contracts.
                Please try again in a few moments.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if TELEMETRY_AVAILABLE:
            log_error_telemetry("circuit_breaker_open", str(e), user_id)
        
    except Exception as e:
        # Catch-all for any other errors
        logger.error(f"Analysis error: {e}", exc_info=True)
        
        st.session_state.api_error_count += 1
        
        # Show branded error message (NO PYTHON TRACEBACK)
        st.markdown("""
        <div class="error-banner">
            <h3 style="margin: 0;">⚠️ Temporary Service Interruption</h3>
            <p style="margin: 0.5rem 0;">
                We're experiencing high demand. Your request couldn't be processed
                at this moment. Please try again shortly.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.info("💡 **Tip**: If this persists, try a shorter contract excerpt or contact support")
        
        if TELEMETRY_AVAILABLE:
            log_error_telemetry("analysis_failure", str(e), user_id)

# ══════════════════════════════════════════════════════════════════════════════
# RESULTS DISPLAY
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.analysis_complete and st.session_state.last_analysis_result:
    result = st.session_state.last_analysis_result
    
    st.divider()
    
    if not st.session_state.show_redlined_view:
        st.markdown("## 📊 Analysis Results")
        
        # Use modular views if available
        if VIEWS_AVAILABLE:
            render_risk_gauge(result)
            render_flagged_clauses(result)
        else:
            # Fallback inline display
            st.metric("Risk Score", f"{result['risk_score']}/100")
            st.progress(result['risk_score'] / 100)
            
            st.markdown("### 📝 Summary")
            st.info(result['summary'])
            
            if result['flagged_clauses']:
                st.markdown(f"### 🚨 {len(result['flagged_clauses'])} Flagged Clause(s)")
                for i, clause in enumerate(result['flagged_clauses'], 1):
                    with st.expander(f"{i}. {clause['category']} — {clause['severity']}"):
                        st.code(clause['clause_text'], language=None)
                        st.markdown(f"**Plain English:** {clause['plain_english']}")
        
        legal_text = result.get('disclaimer', "This analysis is for informational purposes only.")
        st.warning(f"⚖️ **Legal Notice:** {legal_text}")
        
    else:
        # Redlined view
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
