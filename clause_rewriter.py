"""
clause_rewriter.py — Safe-Text Clause Rewriter
Purpose: Generate compliant alternative language for predatory clauses
Features:
- Low-temperature LLM calls for deterministic suggestions
- Jurisdiction-aware rewriting (Federal, CCPA, GDPR)
- Category-specific rewriting strategies
- Before/after comparison with legal justification
- Multiple alternatives per clause (conservative, balanced, user-friendly)
"""

import logging
import os
from typing import List, Optional, Dict
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

try:
    from jurisdictional_rules import Jurisdiction
except ImportError:
    # Fallback if jurisdictional_rules not available
    class Jurisdiction(Enum):
        FEDERAL = "federal"
        CALIFORNIA = "california"
        EUROPE = "europe"

load_dotenv()
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

REWRITER_TEMPERATURE = 0.3  # Low temperature for consistency
REWRITER_MODEL_GROQ = "llama-3.3-70b-versatile"
REWRITER_MODEL_OPENAI = "gpt-4o-mini"


# ══════════════════════════════════════════════════════════════════════════════
# REWRITING STRATEGIES
# ══════════════════════════════════════════════════════════════════════════════

class RewriteStyle(Enum):
    """Different rewriting approaches"""
    CONSERVATIVE = "conservative"  # Minimal changes, keep business protections
    BALANCED = "balanced"  # Fair to both parties
    USER_FRIENDLY = "user_friendly"  # Maximum consumer protection


# Category-specific rewriting guidance
CATEGORY_GUIDANCE = {
    "Arbitration": {
        "issue": "Mandatory arbitration waiving right to court and class actions",
        "solution": "Make arbitration optional, preserve class action rights, allow court access",
        "example": "Either party may resolve disputes through arbitration OR court proceedings. Class action rights are preserved."
    },
    "Data Sharing": {
        "issue": "Sharing/selling personal data without explicit consent",
        "solution": "Require opt-in consent, provide opt-out mechanism, limit to necessary purposes",
        "example": "We will not share your personal information with third parties without your explicit opt-in consent. You may opt out at any time."
    },
    "Gag Clause": {
        "issue": "Non-disparagement preventing negative reviews",
        "solution": "Remove non-disparagement entirely (often illegal), allow honest reviews",
        "example": "You are free to share honest reviews and feedback about our service publicly."
    },
    "Auto-Renewal": {
        "issue": "Automatic renewal without clear disclosure or easy cancellation",
        "solution": "Clear disclosure, easy cancellation in same medium, advance notice",
        "example": "Subscriptions renew automatically. You can cancel anytime with one click. We'll send a reminder 7 days before renewal."
    },
    "Unilateral Modification": {
        "issue": "Changing terms without notice or consent",
        "solution": "Require advance notice (30+ days), allow opt-out with refund",
        "example": "We will provide 30 days advance notice of material changes. You may opt out and receive a prorated refund if you disagree."
    },
    "Limitation of Liability": {
        "issue": "Liability capped at unreasonably low amounts ($50-$100)",
        "solution": "Reasonable cap (12 months fees) or remove cap entirely",
        "example": "Our liability is limited to the fees you paid in the preceding 12 months."
    },
    "IP Rights": {
        "issue": "Claiming ownership or perpetual license to user content",
        "solution": "Limited license for service operation only, user retains ownership",
        "example": "You retain all ownership rights to your content. You grant us a limited license to display your content as necessary to provide the service."
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RewrittenClause:
    """Alternative compliant language for a predatory clause"""
    original_text: str
    rewritten_text: str
    style: RewriteStyle
    category: str
    jurisdiction: Jurisdiction
    legal_justification: str
    improvements: List[str]
    remaining_concerns: Optional[List[str]] = None


@dataclass
class RewriteResult:
    """Complete rewrite result with multiple alternatives"""
    original_clause: str
    category: str
    severity: str
    alternatives: List[RewrittenClause]
    provider_used: str
    processing_time_ms: int


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def get_rewriter_system_prompt(
    category: str,
    jurisdiction: Jurisdiction,
    style: RewriteStyle
) -> str:
    """Generate system prompt for clause rewriting"""
    
    base_prompt = """You are a consumer-rights attorney specializing in rewriting predatory contract clauses into fair, compliant language.

Your goal: Transform one-sided, harmful clauses into balanced language that:
1. Protects consumer rights
2. Complies with applicable law
3. Remains commercially reasonable for the business
4. Uses clear, plain English (no legalese)

CRITICAL RULES:
- Output ONLY valid JSON, no markdown, no preamble
- Be specific and actionable
- Cite relevant laws when applicable
- Explain WHY your rewrite is better
"""
    
    # Add category-specific guidance
    if category in CATEGORY_GUIDANCE:
        guidance = CATEGORY_GUIDANCE[category]
        base_prompt += f"""

CATEGORY-SPECIFIC GUIDANCE ({category}):
Issue: {guidance['issue']}
Solution: {guidance['solution']}
Example: "{guidance['example']}"
"""
    
    # Add jurisdiction-specific requirements
    jurisdiction_guidance = {
        Jurisdiction.FEDERAL: """
FEDERAL COMPLIANCE:
- Consumer Review Fairness Act PROHIBITS non-disparagement clauses
- TCPA requires express written consent for marketing
- FTC Negative Option Rule requires clear auto-renewal disclosure
- Unconscionable limitation of liability may be void
""",
        Jurisdiction.CALIFORNIA: """
CALIFORNIA (CCPA) COMPLIANCE:
- CCPA requires "Do Not Sell My Personal Information" opt-out
- Auto-renewal requires affirmative consent and easy cancellation
- Non-disparagement clauses are VOID (Cal. Civ. Code § 1670.8)
- Must disclose data collection purposes and categories
""",
        Jurisdiction.EUROPE: """
GDPR COMPLIANCE:
- Consent must be freely given, specific, informed, and unambiguous
- Must provide right to erasure (right to be forgotten)
- Must provide data portability in machine-readable format
- Cannot require waiver of GDPR rights as condition of service
- Cross-border transfers require adequacy decision or safeguards
"""
    }
    
    base_prompt += jurisdiction_guidance.get(jurisdiction, "")
    
    # Add style-specific instructions
    style_guidance = {
        RewriteStyle.CONSERVATIVE: """
REWRITING STYLE: Conservative
- Make MINIMAL changes to achieve compliance
- Preserve business protections where legally permissible
- Focus on removing illegal/unconscionable provisions only
- Keep formal legal language if it's clear
""",
        RewriteStyle.BALANCED: """
REWRITING STYLE: Balanced
- Create fair terms for both parties
- Remove one-sided provisions
- Use clear language but maintain necessary business protections
- Aim for industry-standard fairness
""",
        RewriteStyle.USER_FRIENDLY: """
REWRITING STYLE: User-Friendly
- Maximize consumer protection
- Use extremely plain English (8th grade reading level)
- Remove all unnecessary legal jargon
- Err on side of consumer rights
- Make terms as transparent as possible
"""
    }
    
    base_prompt += style_guidance.get(style, style_guidance[RewriteStyle.BALANCED])
    
    # JSON format specification
    base_prompt += """

JSON OUTPUT FORMAT:
{
  "rewritten": "The rewritten clause text in plain English",
  "justification": "1-2 sentence explanation of why this is better and compliant",
  "improvements": ["Improvement 1", "Improvement 2", "Improvement 3"],
  "concerns": ["Any remaining concern (optional)"]
}

EXAMPLES OF GOOD REWRITES:

Original (Arbitration): "You waive your right to sue in court and agree to binding arbitration."
Rewritten: "Disputes may be resolved through mediation, arbitration, or court proceedings. You retain all legal rights including the right to participate in class actions."
Justification: "Preserves consumer access to courts and class actions as required by consumer protection laws."

Original (Data Sharing): "We may share your data with third parties for any purpose."
Rewritten: "We will not share your personal information with third parties without your explicit opt-in consent. You can withdraw consent at any time in your privacy settings."
Justification: "Complies with GDPR/CCPA requirement for affirmative consent and provides easy opt-out mechanism."

Original (Limitation): "Our liability is capped at $50."
Rewritten: "Our liability for service failures is limited to the fees you paid in the preceding 12 months. This limitation does not apply to liability for gross negligence or willful misconduct."
Justification: "Sets a reasonable cap based on actual value received while preserving accountability for egregious conduct."
"""
    
    return base_prompt


def get_rewriter_user_prompt(clause_text: str, severity: str) -> str:
    """Generate user prompt for clause rewriting"""
    return f"""Rewrite this clause:

SEVERITY: {severity}
ORIGINAL CLAUSE:
"{clause_text}"

Provide the JSON output with your rewritten clause, justification, and improvements."""


# ══════════════════════════════════════════════════════════════════════════════
# CLAUSE REWRITER ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ClauseRewriter:
    """
    LLM-powered clause rewriter for generating compliant alternatives.
    """
    
    def __init__(
        self,
        provider: str = "groq",
        groq_key: Optional[str] = None,
        openai_key: Optional[str] = None
    ):
        """
        Initialize clause rewriter.
        
        Args:
            provider: "groq" or "openai"
            groq_key: Groq API key
            openai_key: OpenAI API key
        """
        self.provider = provider.lower()
        
        # Fetch keys
        try:
            import streamlit as st
            st_groq = st.secrets.get("GROQ_API_KEY")
            st_openai = st.secrets.get("OPENAI_API_KEY")
        except:
            st_groq = None
            st_openai = None
        
        self.groq_key = groq_key or st_groq or os.getenv("GROQ_API_KEY")
        self.openai_key = openai_key or st_openai or os.getenv("OPENAI_API_KEY")
        
        # Initialize clients
        if self.provider == "groq" and self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)
            logger.info("✅ Groq rewriter initialized")
        else:
            self.groq_client = None
        
        if self.provider == "openai" and self.openai_key:
            self.openai_client = OpenAI(api_key=self.openai_key)
            logger.info("✅ OpenAI rewriter initialized")
        else:
            self.openai_client = None
        
        if not self.groq_client and not self.openai_client:
            raise ValueError("At least one API key (Groq or OpenAI) required for rewriter")
    
    def rewrite_clause(
        self,
        clause_text: str,
        category: str,
        severity: str,
        jurisdiction: Jurisdiction = Jurisdiction.FEDERAL,
        styles: Optional[List[RewriteStyle]] = None
    ) -> RewriteResult:
        """
        Rewrite a predatory clause into compliant alternatives.
        
        Args:
            clause_text: Original clause text
            category: Clause category (e.g., "Arbitration", "Data Sharing")
            severity: Severity level
            jurisdiction: Legal jurisdiction
            styles: List of rewriting styles (defaults to all 3)
            
        Returns:
            RewriteResult with alternatives
        """
        import time
        import json
        
        start_time = time.time()
        
        # Default to all styles if not specified
        if styles is None:
            styles = [RewriteStyle.CONSERVATIVE, RewriteStyle.BALANCED, RewriteStyle.USER_FRIENDLY]
        
        alternatives = []
        
        for style in styles:
            try:
                # Generate system prompt
                system_prompt = get_rewriter_system_prompt(category, jurisdiction, style)
                user_prompt = get_rewriter_user_prompt(clause_text, severity)
                
                # Call LLM
                if self.provider == "groq" and self.groq_client:
                    response = self.groq_client.chat.completions.create(
                        model=REWRITER_MODEL_GROQ,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=REWRITER_TEMPERATURE,
                        response_format={"type": "json_object"}
                    )
                    raw_json = response.choices[0].message.content
                    provider_used = "groq"
                
                elif self.provider == "openai" and self.openai_client:
                    response = self.openai_client.chat.completions.create(
                        model=REWRITER_MODEL_OPENAI,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=REWRITER_TEMPERATURE,
                        response_format={"type": "json_object"}
                    )
                    raw_json = response.choices[0].message.content
                    provider_used = "openai"
                
                else:
                    raise ValueError(f"Provider {self.provider} not available")
                
                # Parse response
                data = json.loads(raw_json)
                
                rewritten = RewrittenClause(
                    original_text=clause_text,
                    rewritten_text=data.get("rewritten", ""),
                    style=style,
                    category=category,
                    jurisdiction=jurisdiction,
                    legal_justification=data.get("justification", ""),
                    improvements=data.get("improvements", []),
                    remaining_concerns=data.get("concerns")
                )
                
                alternatives.append(rewritten)
                
                logger.debug(f"Generated {style.value} alternative for {category}")
                
            except Exception as e:
                logger.error(f"Failed to generate {style.value} alternative: {e}")
                # Continue with other styles
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return RewriteResult(
            original_clause=clause_text,
            category=category,
            severity=severity,
            alternatives=alternatives,
            provider_used=provider_used,
            processing_time_ms=processing_time_ms
        )


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_clause_rewriter(provider: str = "groq") -> ClauseRewriter:
    """Get a ClauseRewriter instance"""
    return ClauseRewriter(provider=provider)


def format_rewrite_comparison(original: str, rewritten: str) -> str:
    """Format before/after comparison as HTML"""
    return f"""
<div style="padding: 1rem; background: #f8f9fa; border-radius: 8px; margin: 1rem 0;">
    <div style="margin-bottom: 1rem;">
        <strong style="color: #dc3545;">❌ BEFORE (Predatory):</strong>
        <p style="margin: 0.5rem 0; padding: 0.5rem; background: #fff3cd; border-left: 3px solid #dc3545;">
            {original}
        </p>
    </div>
    <div>
        <strong style="color: #28a745;">✅ AFTER (Compliant):</strong>
        <p style="margin: 0.5rem 0; padding: 0.5rem; background: #d4edda; border-left: 3px solid #28a745;">
            {rewritten}
        </p>
    </div>
</div>
"""
