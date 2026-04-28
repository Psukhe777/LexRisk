"""
email_router.py — Attorney Email Routing System
Purpose: Forward contract analysis to attorneys via Resend API
Features:
- Resend API integration for reliable email delivery
- HTML email templates with professional formatting
- Attorney contact management
- Analysis summary packaging
- Attachment support (PDFs, CSVs)
- Delivery tracking and error handling
"""

import logging
import os
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    resend = None

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_FROM_EMAIL = "noreply@lexrisk.com"  # Update with your verified domain
SUBJECT_TEMPLATE = "LexRisk Analysis: {contract_name} - {risk_level} Risk"


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AttorneyContact:
    """Attorney contact information"""
    name: str
    email: str
    firm: str
    specialization: str
    jurisdiction: Optional[str] = None


@dataclass
class EmailResult:
    """Result from sending email"""
    success: bool
    message_id: Optional[str]
    error_message: Optional[str]
    sent_at: str
    recipient: str


# ══════════════════════════════════════════════════════════════════════════════
# ATTORNEY REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

# Sample attorney contacts (replace with real contacts)
ATTORNEY_REGISTRY: List[AttorneyContact] = [
    AttorneyContact(
        name="Jane Smith, Esq.",
        email="jane.smith@consumerlawfirm.com",
        firm="Consumer Rights Law Group",
        specialization="Consumer Protection",
        jurisdiction="Federal"
    ),
    AttorneyContact(
        name="Robert Chen, Esq.",
        email="rchen@californiadata.law",
        firm="California Privacy Advocates",
        specialization="Data Privacy (CCPA)",
        jurisdiction="California"
    ),
    AttorneyContact(
        name="Maria Garcia, Esq.",
        email="mgarcia@eugdpr.legal",
        firm="European Data Rights Firm",
        specialization="GDPR Compliance",
        jurisdiction="Europe"
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def get_attorney_email_html(
    attorney_name: str,
    contract_name: str,
    risk_score: int,
    risk_level: str,
    flagged_clause_count: int,
    jurisdiction: str,
    summary: str,
    top_violations: List[Dict],
    liability_estimate: Optional[str] = None,
    client_email: Optional[str] = None
) -> str:
    """
    Generate HTML email template for attorney.
    
    Args:
        attorney_name: Attorney's name
        contract_name: Name of contract being analyzed
        risk_score: Risk score (0-100)
        risk_level: LOW, MEDIUM, HIGH, CRITICAL
        flagged_clause_count: Number of violations
        jurisdiction: Legal jurisdiction
        summary: Analysis summary
        top_violations: Top 3-5 violations
        liability_estimate: Optional liability calculation
        client_email: Optional client contact
        
    Returns:
        HTML email content
    """
    
    # Risk level colors
    risk_colors = {
        "LOW": "#28a745",
        "MEDIUM": "#ffc107",
        "HIGH": "#fd7e14",
        "CRITICAL": "#dc3545"
    }
    
    risk_color = risk_colors.get(risk_level, "#6c757d")
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 650px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px 8px 0 0;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 0 0 8px 8px;
        }}
        .greeting {{
            margin-bottom: 20px;
        }}
        .risk-badge {{
            display: inline-block;
            background: {risk_color};
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
            margin: 10px 0;
        }}
        .metric-box {{
            background: white;
            border-left: 4px solid {risk_color};
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .metric-box h3 {{
            margin: 0 0 10px 0;
            font-size: 16px;
            color: #495057;
        }}
        .metric-box .value {{
            font-size: 32px;
            font-weight: 700;
            color: {risk_color};
            margin: 0;
        }}
        .violations {{
            background: white;
            padding: 20px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .violation-item {{
            border-left: 3px solid #dc3545;
            padding: 10px 15px;
            margin: 10px 0;
            background: #fff3cd;
        }}
        .violation-category {{
            font-weight: 600;
            color: #dc3545;
        }}
        .cta-button {{
            display: inline-block;
            background: {risk_color};
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            color: #6c757d;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚖️ LexRisk Contract Analysis Report</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">AI-Powered Predatory Clause Detection</p>
    </div>
    
    <div class="content">
        <div class="greeting">
            <p>Dear {attorney_name},</p>
            <p>A new contract analysis has been flagged for legal review. The contract "<strong>{contract_name}</strong>" has been analyzed and shows significant compliance concerns requiring attorney evaluation.</p>
        </div>
        
        <div class="metric-box">
            <h3>Risk Assessment</h3>
            <p class="value">{risk_score}/100</p>
            <span class="risk-badge">{risk_level} RISK</span>
        </div>
        
        <div class="metric-box">
            <h3>Analysis Summary</h3>
            <p><strong>Jurisdiction:</strong> {jurisdiction}</p>
            <p><strong>Flagged Clauses:</strong> {flagged_clause_count}</p>
            <p><strong>Analysis Date:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}</p>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 4px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Executive Summary</h3>
            <p>{summary}</p>
        </div>
"""
    
    # Add top violations
    if top_violations:
        html += """
        <div class="violations">
            <h3 style="margin-top: 0;">⚠️ Critical Violations Detected</h3>
"""
        for violation in top_violations[:5]:
            category = violation.get('category', 'Unknown')
            severity = violation.get('severity', 'MEDIUM')
            explanation = violation.get('plain_english', 'No explanation provided')
            
            html += f"""
            <div class="violation-item">
                <div class="violation-category">{category} ({severity})</div>
                <p style="margin: 5px 0 0 0; font-size: 14px;">{explanation}</p>
            </div>
"""
        html += """
        </div>
"""
    
    # Add liability estimate if available
    if liability_estimate:
        html += f"""
        <div class="metric-box" style="border-left-color: #dc3545;">
            <h3>💰 Estimated Liability Exposure</h3>
            <p class="value" style="font-size: 24px; color: #dc3545;">{liability_estimate}</p>
            <p style="font-size: 14px; color: #6c757d; margin: 5px 0 0 0;">Based on statutory penalties and class action modeling</p>
        </div>
"""
    
    # Add client contact if available
    if client_email:
        html += f"""
        <div style="background: #e7f3ff; padding: 15px; border-radius: 4px; margin: 20px 0;">
            <h4 style="margin-top: 0;">📧 Client Contact</h4>
            <p style="margin: 5px 0;"><a href="mailto:{client_email}" style="color: #667eea;">{client_email}</a></p>
        </div>
"""
    
    # Add call to action
    html += """
        <div style="margin: 30px 0; text-align: center;">
            <p><strong>Full analysis report and litigation shield PDF attached.</strong></p>
            <p style="font-size: 14px; color: #6c757d;">This analysis is for attorney review only and does not constitute legal advice to the client.</p>
        </div>
    </div>
    
    <div class="footer">
        <p><strong>LexRisk</strong> - AI-Powered Contract Analysis</p>
        <p>Powered by Babylon Studio | <a href="https://lexrisk.com" style="color: #667eea;">lexrisk.com</a></p>
        <p style="margin-top: 15px; font-size: 11px;">
            This email contains confidential legal information. If you are not the intended recipient, 
            please delete this email immediately and notify the sender.
        </p>
    </div>
</body>
</html>
"""
    
    return html


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL ROUTER
# ══════════════════════════════════════════════════════════════════════════════

class EmailRouter:
    """
    Email routing system for attorney referrals.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize email router.
        
        Args:
            api_key: Resend API key (auto-detect if None)
        """
        if not RESEND_AVAILABLE:
            raise ImportError(
                "Resend is required for email routing. "
                "Install with: pip install resend"
            )
        
        # Fetch API key
        try:
            import streamlit as st
            st_key = st.secrets.get("RESEND_API_KEY")
        except:
            st_key = None
        
        self.api_key = api_key or st_key or os.getenv("RESEND_API_KEY")
        
        if not self.api_key:
            raise ValueError("RESEND_API_KEY not found in environment or Streamlit secrets")
        
        # Initialize Resend
        resend.api_key = self.api_key
        logger.info("✅ Resend email router initialized")
    
    def send_to_attorney(
        self,
        attorney: AttorneyContact,
        analysis_result: Dict,
        contract_name: str = "Untitled Contract",
        client_email: Optional[str] = None,
        attachments: Optional[List[Dict]] = None
    ) -> EmailResult:
        """
        Send analysis to attorney via email.
        
        Args:
            attorney: AttorneyContact object
            analysis_result: Analysis result dictionary
            contract_name: Name of contract
            client_email: Optional client email
            attachments: Optional list of attachments [{"filename": "report.pdf", "content": bytes}]
            
        Returns:
            EmailResult with delivery status
        """
        try:
            # Extract analysis data
            risk_score = analysis_result.get('risk_score', 0)
            risk_level = analysis_result.get('risk_level', 'UNKNOWN')
            flagged_clauses = analysis_result.get('flagged_clauses', [])
            summary = analysis_result.get('summary', 'No summary available')
            jurisdiction = analysis_result.get('jurisdiction', 'Federal')
            
            # Get liability estimate if available
            liability_estimate = None
            if 'liability_report' in analysis_result:
                liability = analysis_result['liability_report']
                liability_estimate = f"${liability.get('total_liability_expected', 0):,}"
            
            # Convert jurisdiction enum to string if needed
            if hasattr(jurisdiction, 'value'):
                jurisdiction = jurisdiction.value.upper()
            
            # Generate HTML email
            html_content = get_attorney_email_html(
                attorney_name=attorney.name,
                contract_name=contract_name,
                risk_score=risk_score,
                risk_level=risk_level,
                flagged_clause_count=len(flagged_clauses),
                jurisdiction=jurisdiction,
                summary=summary,
                top_violations=flagged_clauses,
                liability_estimate=liability_estimate,
                client_email=client_email
            )
            
            # Prepare email
            subject = SUBJECT_TEMPLATE.format(
                contract_name=contract_name,
                risk_level=risk_level
            )
            
            email_params = {
                "from": DEFAULT_FROM_EMAIL,
                "to": attorney.email,
                "subject": subject,
                "html": html_content
            }
            
            # Add attachments if provided
            if attachments:
                email_params["attachments"] = attachments
            
            # Send via Resend
            response = resend.Emails.send(email_params)
            
            logger.info(f"✅ Email sent to {attorney.email}: {response['id']}")
            
            return EmailResult(
                success=True,
                message_id=response['id'],
                error_message=None,
                sent_at=datetime.now().isoformat(),
                recipient=attorney.email
            )
            
        except Exception as e:
            logger.error(f"Failed to send email to {attorney.email}: {e}")
            
            return EmailResult(
                success=False,
                message_id=None,
                error_message=str(e),
                sent_at=datetime.now().isoformat(),
                recipient=attorney.email
            )
    
    def get_attorney_by_jurisdiction(self, jurisdiction: str) -> Optional[AttorneyContact]:
        """
        Get recommended attorney for jurisdiction.
        
        Args:
            jurisdiction: Legal jurisdiction
            
        Returns:
            AttorneyContact or None
        """
        jurisdiction_lower = jurisdiction.lower()
        
        for attorney in ATTORNEY_REGISTRY:
            if attorney.jurisdiction and jurisdiction_lower in attorney.jurisdiction.lower():
                return attorney
        
        # Default to first attorney if no match
        return ATTORNEY_REGISTRY[0] if ATTORNEY_REGISTRY else None
    
    def get_all_attorneys(self) -> List[AttorneyContact]:
        """Get list of all registered attorneys"""
        return ATTORNEY_REGISTRY.copy()


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_email_router() -> EmailRouter:
    """Get EmailRouter instance"""
    return EmailRouter()


def is_email_available() -> bool:
    """Check if email functionality is available"""
    if not RESEND_AVAILABLE:
        return False
    
    # Check for API key
    api_key = os.getenv("RESEND_API_KEY")
    try:
        import streamlit as st
        api_key = api_key or st.secrets.get("RESEND_API_KEY")
    except:
        pass
    
    return bool(api_key)


def get_email_status_message() -> str:
    """Get human-readable email availability status"""
    if not RESEND_AVAILABLE:
        return (
            "❌ Email unavailable: resend package not installed. "
            "Install with: pip install resend"
        )
    
    if not is_email_available():
        return (
            "❌ Email unavailable: RESEND_API_KEY not set. "
            "Get your API key at: https://resend.com"
        )
    
    return "✅ Email routing available (Resend)"
