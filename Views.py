"""
views.py — Modular UI Components for LexRisk
Extracts visualization logic from main app for cleaner architecture.

Components:
- Risk gauge visualization
- Flagged clauses display
- Hero banner
- Streaming clause renderer
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, List, Any, Iterator
import time


def render_hero():
    """Render hero banner"""
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


def create_risk_gauge(score: int) -> go.Figure:
    """
    Create interactive risk gauge visualization.
    
    Args:
        score: Risk score 0-100
    
    Returns:
        Plotly figure object
    """
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


def render_risk_gauge(result: Dict[str, Any]):
    """
    Render complete risk gauge section with metrics.
    
    Args:
        result: Analysis result dictionary
    """
    col1, col2 = st.columns([2, 1])
    
    with col1:
        gauge_fig = create_risk_gauge(result['risk_score'])
        st.plotly_chart(gauge_fig, use_container_width=True)
    
    with col2:
        st.markdown("### Key Metrics")
        
        # Risk level with color coding
        risk_class_map = {
            'CRITICAL': 'risk-critical',
            'HIGH': 'risk-high',
            'MEDIUM': 'risk-medium',
            'LOW': 'risk-low'
        }
        risk_class = risk_class_map.get(result['risk_level'], 'risk-low')
        
        st.markdown(
            f'<p class="{risk_class}">{result["risk_level"]}</p>', 
            unsafe_allow_html=True
        )
        
        st.metric("Risk Score", f"{result['risk_score']}/100")
        st.metric("Flagged Clauses", len(result['flagged_clauses']))
        
        # Recommendation with emoji
        rec_emoji_map = {
            "SIGN": "✅",
            "NEGOTIATE": "⚠️",
            "AVOID": "🚫"
        }
        rec_emoji = rec_emoji_map.get(result['recommendation'], "❓")
        st.metric("Recommendation", f"{rec_emoji} {result['recommendation']}")
    
    st.progress(result['risk_score'] / 100)


def get_severity_icon(severity: str) -> str:
    """Get emoji icon for severity level"""
    severity_icons = {
        'LOW': '🟢',
        'MEDIUM': '🟡',
        'HIGH': '🟠',
        'CRITICAL': '🔴'
    }
    return severity_icons.get(severity, '⚪')


def render_flagged_clauses(result: Dict[str, Any]):
    """
    Render flagged clauses section.
    
    Args:
        result: Analysis result dictionary
    """
    st.markdown("### 📝 Executive Summary")
    st.info(result['summary'])
    
    if result['flagged_clauses']:
        st.divider()
        st.markdown(f"### 🚨 {len(result['flagged_clauses'])} Flagged Clause(s)")
        
        for i, clause in enumerate(result['flagged_clauses'], 1):
            severity_icon = get_severity_icon(clause['severity'])
            
            with st.expander(
                f"{severity_icon} {i}. {clause['category']} — {clause['severity']}",
                expanded=(clause['severity'] in ['CRITICAL', 'HIGH'])
            ):
                st.markdown("**📋 Clause Text:**")
                st.code(clause['clause_text'], language=None)
                
                st.markdown("**💬 Plain English:**")
                st.write(clause['plain_english'])
                
                st.markdown("**⚠️ Red Flag:**")
                st.error(clause['red_flag'])
    else:
        st.success("✅ No predatory clauses detected!")


def stream_clause_generator(clauses: List[Dict[str, Any]]) -> Iterator[str]:
    """
    Generator that yields HTML for each clause with simulated streaming.
    
    Args:
        clauses: List of flagged clause dictionaries
    
    Yields:
        HTML strings for progressive rendering
    """
    for i, clause in enumerate(clauses, 1):
        severity_icon = get_severity_icon(clause['severity'])
        
        html = f"""
        <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; 
                    margin: 1rem 0; border-left: 4px solid 
                    {'#ff4444' if clause['severity'] == 'CRITICAL' else
                     '#ff8800' if clause['severity'] == 'HIGH' else
                     '#ffcc00' if clause['severity'] == 'MEDIUM' else '#44cc44'};">
            <h4>{severity_icon} {i}. {clause['category']} — {clause['severity']}</h4>
            <p><strong>Clause Text:</strong></p>
            <pre style="background: white; padding: 0.5rem; border-radius: 4px; 
                        overflow-x: auto;">{clause['clause_text'][:200]}...</pre>
            <p><strong>Plain English:</strong> {clause['plain_english']}</p>
            <p><strong>⚠️ Red Flag:</strong> {clause['red_flag']}</p>
        </div>
        """
        
        yield html
        time.sleep(0.1)  # Simulate streaming delay


def render_streaming_clauses(result: Dict[str, Any]):
    """
    Render flagged clauses with streaming effect.
    
    Args:
        result: Analysis result dictionary
    """
    st.markdown("### 📝 Executive Summary")
    st.info(result['summary'])
    
    if result['flagged_clauses']:
        st.divider()
        st.markdown(f"### 🚨 Detecting Predatory Clauses...")
        
        # Create streaming container
        stream_container = st.empty()
        accumulated_html = []
        
        for html_chunk in stream_clause_generator(result['flagged_clauses']):
            accumulated_html.append(html_chunk)
            stream_container.markdown(
                ''.join(accumulated_html),
                unsafe_allow_html=True
            )
        
        # Update header after streaming completes
        st.markdown(f"### ✅ {len(result['flagged_clauses'])} Clause(s) Flagged")
    else:
        st.success("✅ No predatory clauses detected!")


def render_analysis_metrics(result: Dict[str, Any]):
    """
    Render analysis metadata and performance metrics.
    
    Args:
        result: Analysis result dictionary
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Engine Used",
            result.get('_provider_used', result.get('engine_used', 'N/A')).upper()
        )
    
    with col2:
        processing_time = result.get('_processing_time', 0)
        st.metric(
            "Processing Time",
            f"{processing_time:.2f}s" if processing_time > 0 else "Cached"
        )
    
    with col3:
        st.metric(
            "Contract Type",
            result.get('contract_type', 'Unknown').replace('_', ' ').title()
        )
    
    with col4:
        breaker_state = result.get('_breaker_state', 'n/a')
        state_emoji = "🟢" if breaker_state == "closed" else "🟡" if breaker_state == "half_open" else "🔴"
        st.metric(
            "System Status",
            f"{state_emoji} {breaker_state.title()}" if breaker_state != 'n/a' else "N/A"
        )


def render_upgrade_prompt(current_tier: str = "free"):
    """
    Render contextual upgrade prompt.
    
    Args:
        current_tier: User's current subscription tier
    """
    if current_tier == "free":
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 1.5rem; border-radius: 12px; margin: 2rem 0; 
                    text-align: center;">
            <h3 style="margin: 0;">🚀 Upgrade to Pro</h3>
            <p style="margin: 0.5rem 0;">
                Analyze unlimited pages, access priority processing, and export reports.
            </p>
            <a href="/signup" style="display: inline-block; margin-top: 1rem; 
               padding: 0.75rem 2rem; background: white; color: #667eea; 
               border-radius: 8px; text-decoration: none; font-weight: bold;">
                View Pro Plans →
            </a>
        </div>
        """, unsafe_allow_html=True)


def render_error_state(error_type: str = "generic", details: str = ""):
    """
    Render branded error state UI.
    
    Args:
        error_type: Type of error (generic, rate_limit, upload, api)
        details: Additional error details
    """
    error_messages = {
        "generic": {
            "title": "⚠️ Temporary Service Interruption",
            "message": "We're experiencing high demand. Please try again shortly."
        },
        "rate_limit": {
            "title": "🛑 Daily Scan Limit Reached",
            "message": "You've reached your daily analysis limit. Upgrade to Pro for 50 scans/day."
        },
        "upload": {
            "title": "📄 Upload Error",
            "message": f"File upload failed: {details}"
        },
        "api": {
            "title": "🔌 API Service Unavailable",
            "message": "Our AI service is temporarily unavailable. Please try again in a few moments."
        },
        "maintenance": {
            "title": "⚠️ System Maintenance",
            "message": "LexRisk is currently processing an unusually high volume of contracts."
        }
    }
    
    error_config = error_messages.get(error_type, error_messages["generic"])
    
    st.markdown(f"""
    <div class="error-banner">
        <h3 style="margin: 0;">{error_config['title']}</h3>
        <p style="margin: 0.5rem 0;">
            {error_config['message']}
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_loading_stages():
    """Render multi-stage loading animation"""
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


# ══════════════════════════════════════════════════════════════════════════════
# ADVANCED STREAMING COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

class StreamingClauseRenderer:
    """
    Advanced streaming renderer for real-time clause display.
    Simulates progressive analysis output.
    """
    
    def __init__(self, container=None):
        self.container = container or st.empty()
        self.rendered_clauses = []
    
    def add_clause(self, clause: Dict[str, Any], index: int):
        """Add a clause to the streaming display"""
        severity_icon = get_severity_icon(clause['severity'])
        
        severity_color_map = {
            'CRITICAL': '#ff4444',
            'HIGH': '#ff8800',
            'MEDIUM': '#ffcc00',
            'LOW': '#44cc44'
        }
        color = severity_color_map.get(clause['severity'], '#888888')
        
        html = f"""
        <div style="background: #ffffff; padding: 1.5rem; border-radius: 8px; 
                    margin: 1rem 0; border-left: 5px solid {color}; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    animation: slideIn 0.3s ease-out;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0; color: #2d3436;">
                    {severity_icon} {index}. {clause['category']}
                </h4>
                <span style="background: {color}; color: white; padding: 0.25rem 0.75rem; 
                             border-radius: 12px; font-size: 0.85rem; font-weight: bold;">
                    {clause['severity']}
                </span>
            </div>
            
            <div style="margin-top: 1rem; background: #f8f9fa; padding: 1rem; 
                        border-radius: 6px;">
                <strong>📋 Clause Text:</strong>
                <pre style="background: white; padding: 0.75rem; border-radius: 4px; 
                            margin-top: 0.5rem; overflow-x: auto; font-size: 0.9rem; 
                            border: 1px solid #ddd;">{clause['clause_text'][:300]}{'...' if len(clause['clause_text']) > 300 else ''}</pre>
            </div>
            
            <div style="margin-top: 1rem;">
                <strong>💬 Plain English:</strong>
                <p style="margin: 0.5rem 0; color: #555; line-height: 1.6;">
                    {clause['plain_english']}
                </p>
            </div>
            
            <div style="margin-top: 1rem; background: #fff3cd; padding: 1rem; 
                        border-radius: 6px; border-left: 4px solid #ff8800;">
                <strong>⚠️ Red Flag:</strong>
                <p style="margin: 0.5rem 0 0 0; color: #856404;">
                    {clause['red_flag']}
                </p>
            </div>
        </div>
        
        <style>
            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(20px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
        </style>
        """
        
        self.rendered_clauses.append(html)
        self.container.markdown(''.join(self.rendered_clauses), unsafe_allow_html=True)
    
    def render_all(self, clauses: List[Dict[str, Any]], delay: float = 0.3):
        """Render all clauses with streaming effect"""
        for i, clause in enumerate(clauses, 1):
            self.add_clause(clause, i)
            time.sleep(delay)
