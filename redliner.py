"""
redliner.py — Visual Redlining for Predatory Clauses
Highlights dangerous clauses in the contract text with color-coded severity.

Features:
- Fuzzy matching to find clauses even if wording slightly differs
- Color-coded highlighting: GREEN (low), YELLOW (medium), ORANGE (high), RED (critical)
- HTML output with smooth animations
- Tooltip popups with plain-English explanations
"""

import re
from typing import List, Dict
from difflib import SequenceMatcher

# ══════════════════════════════════════════════════════════════════════════════
# SEVERITY COLORS
# ══════════════════════════════════════════════════════════════════════════════

SEVERITY_COLORS = {
    'LOW': {
        'bg': '#d4edda',
        'border': '#c3e6cb',
        'text': '#155724',
        'icon': '🟢'
    },
    'MEDIUM': {
        'bg': '#fff3cd',
        'border': '#ffeaa7',
        'text': '#856404',
        'icon': '🟡'
    },
    'HIGH': {
        'bg': '#ffe5d0',
        'border': '#ffb366',
        'text': '#d63031',
        'icon': '🟠'
    },
    'CRITICAL': {
        'bg': '#f8d7da',
        'border': '#f5c6cb',
        'text': '#721c24',
        'icon': '🔴'
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, remove extra spaces)"""
    return ' '.join(text.lower().split())

def find_clause_in_text(clause_text: str, full_text: str, threshold: float = 0.6) -> tuple:
    """
    Find a clause in the full text using fuzzy matching.
    Returns: (start_index, end_index, match_ratio)
    """
    clause_norm = normalize_text(clause_text)
    full_norm = normalize_text(full_text)
    
    # If clause is very short (< 20 chars), require exact match
    if len(clause_norm) < 20:
        if clause_norm in full_norm:
            idx = full_norm.index(clause_norm)
            return (idx, idx + len(clause_norm), 1.0)
        return (-1, -1, 0.0)
    
    # For longer clauses, use sliding window fuzzy matching
    clause_len = len(clause_norm)
    best_match = (0, 0, 0.0)
    
    # Slide through the text
    for i in range(len(full_norm) - clause_len + 1):
        window = full_norm[i:i + clause_len]
        ratio = SequenceMatcher(None, clause_norm, window).ratio()
        
        if ratio > best_match[2]:
            best_match = (i, i + clause_len, ratio)
    
    # Return match if above threshold
    if best_match[2] >= threshold:
        return best_match
    
    return (-1, -1, 0.0)

def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;'))

# ══════════════════════════════════════════════════════════════════════════════
# MAIN REDLINING FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def get_redlined_html(contract_text: str, flagged_clauses: List) -> str:
    """
    Generate HTML with highlighted predatory clauses.
    
    Args:
        contract_text: The full contract text
        flagged_clauses: List of FlaggedClause objects or dicts
        
    Returns:
        HTML string with highlighted clauses
    """
    if not contract_text:
        return "<p>No contract text provided.</p>"
    
    if not flagged_clauses:
        return f"""
        <div style="background: #d4edda; padding: 2rem; border-radius: 8px; border: 2px solid #c3e6cb;">
            <h3 style="color: #155724; margin: 0;">✅ Clean Contract</h3>
            <p style="color: #155724; margin: 0.5rem 0 0 0;">
                No predatory clauses detected in this document.
            </p>
        </div>
        <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 8px; margin-top: 1rem; 
                    font-family: 'Courier New', monospace; white-space: pre-wrap; line-height: 1.6;">
            {escape_html(contract_text)}
        </div>
        """
    
    # Build a list of clause positions
    clause_positions = []
    
    for i, clause in enumerate(flagged_clauses):
        # Handle both dict and object types
        if isinstance(clause, dict):
            clause_text = clause.get('clause_text', '')
            severity = clause.get('severity', 'LOW')
            category = clause.get('category', 'Unknown')
            plain_english = clause.get('plain_english', '')
            red_flag = clause.get('red_flag', '')
        else:
            clause_text = clause.clause_text
            severity = clause.severity
            category = clause.category
            plain_english = clause.plain_english
            red_flag = clause.red_flag
        
        # Find clause in text
        start, end, match_ratio = find_clause_in_text(clause_text, contract_text, threshold=0.6)
        
        if start >= 0:  # Found
            clause_positions.append({
                'start': start,
                'end': end,
                'severity': severity,
                'category': category,
                'plain_english': plain_english,
                'red_flag': red_flag,
                'id': i
            })
    
    # Sort by position
    clause_positions.sort(key=lambda x: x['start'])
    
    # Build HTML with highlights
    html_parts = []
    html_parts.append("""
    <style>
        .redline-container {
            background: #ffffff;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            font-family: 'Georgia', serif;
            line-height: 1.8;
            font-size: 1.1rem;
        }
        
        .redline-highlight {
            padding: 2px 4px;
            border-radius: 4px;
            cursor: help;
            transition: all 0.2s ease;
            position: relative;
            display: inline;
        }
        
        .redline-highlight:hover {
            transform: scale(1.02);
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        
        .redline-tooltip {
            visibility: hidden;
            position: absolute;
            z-index: 1000;
            background: #1a1a2e;
            color: white;
            padding: 1rem;
            border-radius: 8px;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            width: 300px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            opacity: 0;
            transition: opacity 0.3s, visibility 0.3s;
        }
        
        .redline-highlight:hover .redline-tooltip {
            visibility: visible;
            opacity: 1;
        }
        
        .redline-stats {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            display: flex;
            justify-content: space-around;
        }
        
        .stat-box {
            text-align: center;
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            display: block;
        }
        
        .stat-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
    </style>
    """)
    
    # Add stats header
    severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for pos in clause_positions:
        severity_counts[pos['severity']] += 1
    
    html_parts.append(f"""
    <div class="redline-stats">
        <div class="stat-box">
            <span class="stat-number">{len(clause_positions)}</span>
            <span class="stat-label">Flagged Clauses</span>
        </div>
        <div class="stat-box">
            <span class="stat-number">🔴 {severity_counts['CRITICAL']}</span>
            <span class="stat-label">Critical</span>
        </div>
        <div class="stat-box">
            <span class="stat-number">🟠 {severity_counts['HIGH']}</span>
            <span class="stat-label">High</span>
        </div>
        <div class="stat-box">
            <span class="stat-number">🟡 {severity_counts['MEDIUM']}</span>
            <span class="stat-label">Medium</span>
        </div>
        <div class="stat-box">
            <span class="stat-number">🟢 {severity_counts['LOW']}</span>
            <span class="stat-label">Low</span>
        </div>
    </div>
    """)
    
    html_parts.append('<div class="redline-container">')
    
    # Build the highlighted text
    last_pos = 0
    for pos in clause_positions:
        # Add text before this clause
        if pos['start'] > last_pos:
            html_parts.append(escape_html(contract_text[last_pos:pos['start']]))
        
        # Add highlighted clause
        colors = SEVERITY_COLORS[pos['severity']]
        clause_text = contract_text[pos['start']:pos['end']]
        
        html_parts.append(f"""
        <span class="redline-highlight" 
              style="background: {colors['bg']}; 
                     border-bottom: 3px solid {colors['border']}; 
                     color: {colors['text']};">
            {escape_html(clause_text)}
            <div class="redline-tooltip">
                <strong>{colors['icon']} {pos['category']}</strong>
                <p style="margin: 0.5rem 0; font-size: 0.9rem;">
                    {escape_html(pos['plain_english'])}
                </p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.85rem; color: #ff6b6b;">
                    ⚠️ {escape_html(pos['red_flag'])}
                </p>
            </div>
        </span>
        """)
        
        last_pos = pos['end']
    
    # Add remaining text
    if last_pos < len(contract_text):
        html_parts.append(escape_html(contract_text[last_pos:]))
    
    html_parts.append('</div>')
    
    # Add legend
    html_parts.append("""
    <div style="margin-top: 2rem; padding: 1rem; background: #f8f9fa; border-radius: 8px;">
        <h4 style="margin: 0 0 1rem 0;">📖 How to Read This Document</h4>
        <p style="margin: 0.5rem 0;">
            <strong>Hover over highlighted text</strong> to see detailed explanations of why each clause is flagged.
        </p>
        <div style="display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap;">
            <span style="background: #d4edda; padding: 0.5rem 1rem; border-radius: 4px;">
                🟢 Low Risk
            </span>
            <span style="background: #fff3cd; padding: 0.5rem 1rem; border-radius: 4px;">
                🟡 Medium Risk
            </span>
            <span style="background: #ffe5d0; padding: 0.5rem 1rem; border-radius: 4px;">
                🟠 High Risk
            </span>
            <span style="background: #f8d7da; padding: 0.5rem 1rem; border-radius: 4px;">
                🔴 Critical Risk
            </span>
        </div>
    </div>
    """)
    
    return ''.join(html_parts)

def get_redlining_summary(flagged_clauses: List) -> str:
    """
    Generate a summary card showing redlining statistics.
    """
    if not flagged_clauses:
        return """
        <div style="background: #d4edda; padding: 1.5rem; border-radius: 8px; text-align: center;">
            <h3 style="color: #155724; margin: 0;">✅ No Clauses Flagged</h3>
            <p style="color: #155724; margin: 0.5rem 0 0 0;">
                This contract appears clean with no predatory clauses detected.
            </p>
        </div>
        """
    
    severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    categories = {}
    
    for clause in flagged_clauses:
        if isinstance(clause, dict):
            severity = clause.get('severity', 'LOW')
            category = clause.get('category', 'Unknown')
        else:
            severity = clause.severity
            category = clause.category
        
        severity_counts[severity] += 1
        categories[category] = categories.get(category, 0) + 1
    
    total = len(flagged_clauses)
    
    # Determine overall risk
    if severity_counts['CRITICAL'] > 0:
        risk_color = '#ff4444'
        risk_text = 'CRITICAL RISK'
    elif severity_counts['HIGH'] > 2:
        risk_color = '#ff8800'
        risk_text = 'HIGH RISK'
    elif severity_counts['MEDIUM'] > 3:
        risk_color = '#ffcc00'
        risk_text = 'MEDIUM RISK'
    else:
        risk_color = '#44cc44'
        risk_text = 'LOW RISK'
    
    html = f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 2rem; border-radius: 12px; color: white; margin: 1rem 0;">
        <h2 style="margin: 0; text-align: center;">🔍 Redlining Analysis</h2>
        <div style="text-align: center; margin: 1.5rem 0;">
            <div style="font-size: 3rem; font-weight: bold; color: {risk_color};">
                {total}
            </div>
            <div style="font-size: 1.2rem; margin-top: 0.5rem;">
                Predatory Clauses Detected
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-top: 1.5rem;">
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; text-align: center;">
                <div style="font-size: 2rem;">🔴</div>
                <div style="font-size: 1.5rem; font-weight: bold;">{severity_counts['CRITICAL']}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Critical</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; text-align: center;">
                <div style="font-size: 2rem;">🟠</div>
                <div style="font-size: 1.5rem; font-weight: bold;">{severity_counts['HIGH']}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">High</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; text-align: center;">
                <div style="font-size: 2rem;">🟡</div>
                <div style="font-size: 1.5rem; font-weight: bold;">{severity_counts['MEDIUM']}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Medium</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; text-align: center;">
                <div style="font-size: 2rem;">🟢</div>
                <div style="font-size: 1.5rem; font-weight: bold;">{severity_counts['LOW']}</div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Low</div>
            </div>
        </div>
        
        <div style="margin-top: 1.5rem; text-align: center; font-size: 1.1rem; font-weight: bold; 
                    background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 8px;">
            Overall Assessment: <span style="color: {risk_color};">{risk_text}</span>
        </div>
    </div>
    """
    
    return html
