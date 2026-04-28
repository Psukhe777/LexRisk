"""
jurisdictional_rules.py — Jurisdictional Compliance Rules Library
Purpose: Provide jurisdiction-specific legal requirements and enhanced risk scoring
Features:
- Federal baseline compliance rules (FTC, TCPA, CAN-SPAM)
- California CCPA/CPRA consumer protection rules
- European GDPR data protection requirements
- Jurisdiction-specific penalty multipliers
- Enhanced clause detection rules per jurisdiction
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# JURISDICTION ENUMERATION
# ══════════════════════════════════════════════════════════════════════════════

class Jurisdiction(Enum):
    """Supported legal jurisdictions"""
    FEDERAL = "federal"
    CALIFORNIA = "california"
    EUROPE = "europe"
    # Future expansion: NEW_YORK, TEXAS, UK, etc.


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class JurisdictionalRule:
    """Single jurisdiction-specific compliance requirement"""
    rule_id: str
    category: str  # Maps to predatory clause categories
    severity: str
    description: str
    legal_citation: str
    penalty_multiplier: float  # Multiplier for base risk score


@dataclass
class JurisdictionProfile:
    """Complete profile for a jurisdiction"""
    jurisdiction: Jurisdiction
    display_name: str
    enhanced_rules: List[JurisdictionalRule]
    prohibited_clauses: List[str]  # Categories that are illegal
    required_disclosures: List[str]
    max_penalty_per_violation: int  # In USD
    system_prompt_addendum: str  # Injected into LLM prompt


# ══════════════════════════════════════════════════════════════════════════════
# FEDERAL (BASELINE) RULES
# ══════════════════════════════════════════════════════════════════════════════

FEDERAL_RULES = [
    JurisdictionalRule(
        rule_id="FED-001",
        category="Arbitration",
        severity="HIGH",
        description="Mandatory arbitration must allow for discovery and cannot limit consumer's right to remedies",
        legal_citation="Federal Arbitration Act, 9 U.S.C. § 2",
        penalty_multiplier=1.0
    ),
    JurisdictionalRule(
        rule_id="FED-002",
        category="Gag Clause",
        severity="CRITICAL",
        description="Non-disparagement clauses that prevent consumer reviews violate FTC Act and CFPB rules",
        legal_citation="Consumer Review Fairness Act, 15 U.S.C. § 45b",
        penalty_multiplier=2.0
    ),
    JurisdictionalRule(
        rule_id="FED-003",
        category="Auto-Renewal",
        severity="HIGH",
        description="Auto-renewal must provide clear disclosure and easy cancellation mechanism",
        legal_citation="FTC Negative Option Rule, 16 CFR Part 425",
        penalty_multiplier=1.5
    ),
    JurisdictionalRule(
        rule_id="FED-004",
        category="Data Sharing",
        severity="HIGH",
        description="Telemarketing requires prior express written consent before sharing consumer data",
        legal_citation="Telephone Consumer Protection Act (TCPA), 47 U.S.C. § 227",
        penalty_multiplier=1.3
    ),
]

FEDERAL_PROFILE = JurisdictionProfile(
    jurisdiction=Jurisdiction.FEDERAL,
    display_name="Federal (U.S. Baseline)",
    enhanced_rules=FEDERAL_RULES,
    prohibited_clauses=["Gag Clause"],  # Consumer Review Fairness Act
    required_disclosures=[
        "Material terms must be clearly disclosed before purchase",
        "Auto-renewal terms must be conspicuous"
    ],
    max_penalty_per_violation=50000,  # FTC Act: up to $50,280 per violation (2024)
    system_prompt_addendum="""
FEDERAL COMPLIANCE REQUIREMENTS (U.S. Baseline):
- The Consumer Review Fairness Act PROHIBITS non-disparagement clauses that prevent consumer reviews. Flag as CRITICAL if present.
- FTC Negative Option Rule requires clear auto-renewal disclosure and easy cancellation. Flag HIGH if missing.
- TCPA requires prior express written consent for telemarketing/data sharing. Flag if violated.
- Limitation of liability below $100 may violate unconscionability standards. Flag CRITICAL.
- Mandatory arbitration must preserve consumer remedies. Flag if discovery or remedies are limited.
"""
)


# ══════════════════════════════════════════════════════════════════════════════
# CALIFORNIA (CCPA/CPRA) RULES
# ══════════════════════════════════════════════════════════════════════════════

CALIFORNIA_RULES = [
    JurisdictionalRule(
        rule_id="CA-001",
        category="Data Sharing",
        severity="CRITICAL",
        description="Must provide explicit opt-out mechanism for sale of personal information",
        legal_citation="California Consumer Privacy Act (CCPA), Cal. Civ. Code § 1798.120",
        penalty_multiplier=3.0
    ),
    JurisdictionalRule(
        rule_id="CA-002",
        category="Data Sharing",
        severity="CRITICAL",
        description="Must disclose categories of personal information collected and purposes",
        legal_citation="CCPA § 1798.100(b)",
        penalty_multiplier=2.5
    ),
    JurisdictionalRule(
        rule_id="CA-003",
        category="Termination",
        severity="HIGH",
        description="Cannot penalize consumers for exercising CCPA rights (no service denial)",
        legal_citation="CCPA § 1798.125",
        penalty_multiplier=2.0
    ),
    JurisdictionalRule(
        rule_id="CA-004",
        category="Auto-Renewal",
        severity="CRITICAL",
        description="Auto-renewal requires affirmative consent, clear terms, and easy cancellation in same medium",
        legal_citation="California Automatic Renewal Law, Bus. & Prof. Code § 17602",
        penalty_multiplier=2.5
    ),
    JurisdictionalRule(
        rule_id="CA-005",
        category="Gag Clause",
        severity="CRITICAL",
        description="Non-disparagement clauses in consumer contracts are void and unenforceable",
        legal_citation="Cal. Civ. Code § 1670.8",
        penalty_multiplier=3.0
    ),
    JurisdictionalRule(
        rule_id="CA-006",
        category="Arbitration",
        severity="CRITICAL",
        description="Mandatory arbitration in employment contracts is unenforceable (PAGA claims)",
        legal_citation="Cal. Labor Code § 2699 (PAGA)",
        penalty_multiplier=2.0
    ),
]

CALIFORNIA_PROFILE = JurisdictionProfile(
    jurisdiction=Jurisdiction.CALIFORNIA,
    display_name="California (CCPA/CPRA)",
    enhanced_rules=CALIFORNIA_RULES,
    prohibited_clauses=["Gag Clause"],  # Cal. Civ. Code § 1670.8
    required_disclosures=[
        "Do Not Sell My Personal Information link required",
        "CCPA privacy notice within 12 months of collection",
        "Auto-renewal terms in clear language before purchase",
        "Categories of personal information collected"
    ],
    max_penalty_per_violation=7500,  # CCPA: $2,500 regular, $7,500 intentional (per violation)
    system_prompt_addendum="""
CALIFORNIA COMPLIANCE REQUIREMENTS (CCPA/CPRA):
- CRITICAL: Data sharing/selling WITHOUT explicit opt-out is a CCPA violation. Flag as CRITICAL if "Do Not Sell" mechanism missing.
- CRITICAL: Non-disparagement clauses are VOID in California (Cal. Civ. Code § 1670.8). Always flag as CRITICAL.
- CRITICAL: Auto-renewal without affirmative consent, clear terms, and easy cancellation violates Bus. & Prof. Code § 17602. Flag as CRITICAL.
- HIGH: Penalizing consumers for exercising CCPA rights (e.g., denying service) violates § 1798.125. Flag as HIGH.
- CRITICAL: Mandatory arbitration waiving PAGA claims in employment contracts is unenforceable. Flag if present.
- Required: Contract must disclose categories of personal information collected and purposes of use.
- Penalty potential: Up to $7,500 per intentional violation.
"""
)


# ══════════════════════════════════════════════════════════════════════════════
# EUROPE (GDPR) RULES
# ══════════════════════════════════════════════════════════════════════════════

EUROPE_RULES = [
    JurisdictionalRule(
        rule_id="EU-001",
        category="Data Sharing",
        severity="CRITICAL",
        description="Data processing requires explicit consent or legitimate interest basis",
        legal_citation="GDPR Article 6 (Lawfulness of processing)",
        penalty_multiplier=4.0
    ),
    JurisdictionalRule(
        rule_id="EU-002",
        category="Data Sharing",
        severity="CRITICAL",
        description="Must provide clear right to erasure (right to be forgotten)",
        legal_citation="GDPR Article 17 (Right to erasure)",
        penalty_multiplier=3.5
    ),
    JurisdictionalRule(
        rule_id="EU-003",
        category="Data Sharing",
        severity="CRITICAL",
        description="Data portability must be provided in structured, machine-readable format",
        legal_citation="GDPR Article 20 (Right to data portability)",
        penalty_multiplier=3.0
    ),
    JurisdictionalRule(
        rule_id="EU-004",
        category="Termination",
        severity="HIGH",
        description="Cannot require waiver of GDPR rights as condition of service",
        legal_citation="GDPR Article 7 (Conditions for consent)",
        penalty_multiplier=3.0
    ),
    JurisdictionalRule(
        rule_id="EU-005",
        category="IP Rights",
        severity="HIGH",
        description="Data subjects retain rights over personal data even if 'licensed' to service",
        legal_citation="GDPR Article 15 (Right of access)",
        penalty_multiplier=2.5
    ),
    JurisdictionalRule(
        rule_id="EU-006",
        category="Unilateral Modification",
        severity="HIGH",
        description="Material changes to data processing require renewed consent",
        legal_citation="GDPR Recital 42 (Consent requirements)",
        penalty_multiplier=2.0
    ),
    JurisdictionalRule(
        rule_id="EU-007",
        category="Data Sharing",
        severity="CRITICAL",
        description="Cross-border data transfers require adequacy decision or safeguards",
        legal_citation="GDPR Chapter V (Transfers of personal data to third countries)",
        penalty_multiplier=4.0
    ),
]

EUROPE_PROFILE = JurisdictionProfile(
    jurisdiction=Jurisdiction.EUROPE,
    display_name="Europe (GDPR)",
    enhanced_rules=EUROPE_RULES,
    prohibited_clauses=[],  # GDPR doesn't prohibit specific clauses, but heavily regulates data
    required_disclosures=[
        "Legal basis for data processing (consent, contract, legitimate interest, etc.)",
        "Data retention periods or criteria",
        "Right to access, rectification, erasure, restriction, portability",
        "Right to object to processing",
        "Right to withdraw consent at any time",
        "Data Protection Officer contact (if applicable)",
        "Right to lodge complaint with supervisory authority"
    ],
    max_penalty_per_violation=20000000,  # GDPR: €20M or 4% global revenue, whichever is higher
    system_prompt_addendum="""
EUROPEAN UNION COMPLIANCE REQUIREMENTS (GDPR):
- CRITICAL: Data processing without explicit consent or legitimate interest basis violates GDPR Article 6. Flag as CRITICAL if legal basis missing.
- CRITICAL: Missing right to erasure (right to be forgotten) violates Article 17. Flag as CRITICAL.
- CRITICAL: Cross-border data transfers without adequacy decision or safeguards violate Chapter V. Flag as CRITICAL if mentioned.
- CRITICAL: Requiring waiver of GDPR rights as condition of service violates Article 7. Flag as CRITICAL.
- HIGH: Material changes to data processing without renewed consent violate consent requirements. Flag as HIGH.
- HIGH: Missing data portability rights violate Article 20. Flag as HIGH.
- Required: Contract must disclose legal basis for processing, retention periods, and all GDPR rights.
- Penalty potential: Up to €20 million OR 4% of global annual revenue (whichever is higher) per violation.
- Note: GDPR has EXTRATERRITORIAL APPLICATION - applies to any company processing EU residents' data.
"""
)


# ══════════════════════════════════════════════════════════════════════════════
# JURISDICTION REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

JURISDICTION_REGISTRY: Dict[Jurisdiction, JurisdictionProfile] = {
    Jurisdiction.FEDERAL: FEDERAL_PROFILE,
    Jurisdiction.CALIFORNIA: CALIFORNIA_PROFILE,
    Jurisdiction.EUROPE: EUROPE_PROFILE,
}


# ══════════════════════════════════════════════════════════════════════════════
# ACCESSOR FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_jurisdiction_profile(jurisdiction: Jurisdiction) -> JurisdictionProfile:
    """
    Get the full compliance profile for a jurisdiction.
    
    Args:
        jurisdiction: Jurisdiction enum value
        
    Returns:
        JurisdictionProfile with rules and requirements
    """
    return JURISDICTION_REGISTRY[jurisdiction]


def get_jurisdiction_by_name(name: str) -> Optional[Jurisdiction]:
    """
    Get jurisdiction enum from display name.
    
    Args:
        name: Display name (e.g., "Federal (U.S. Baseline)")
        
    Returns:
        Jurisdiction enum or None if not found
    """
    name_lower = name.lower()
    
    if "federal" in name_lower or "baseline" in name_lower:
        return Jurisdiction.FEDERAL
    elif "california" in name_lower or "ccpa" in name_lower:
        return Jurisdiction.CALIFORNIA
    elif "europe" in name_lower or "gdpr" in name_lower or "eu" in name_lower:
        return Jurisdiction.EUROPE
    
    return None


def get_jurisdiction_display_names() -> List[str]:
    """Get list of display names for UI dropdown"""
    return [profile.display_name for profile in JURISDICTION_REGISTRY.values()]


def calculate_jurisdictional_penalty_multiplier(
    flagged_category: str,
    jurisdiction: Jurisdiction
) -> float:
    """
    Calculate penalty multiplier for a flagged clause based on jurisdiction.
    
    Args:
        flagged_category: Category of the flagged clause
        jurisdiction: Active jurisdiction
        
    Returns:
        Multiplier to apply to base risk score (1.0 = no change)
    """
    profile = get_jurisdiction_profile(jurisdiction)
    
    # Check if category has specific rule in this jurisdiction
    for rule in profile.enhanced_rules:
        if rule.category == flagged_category:
            return rule.penalty_multiplier
    
    # Check if category is prohibited entirely
    if flagged_category in profile.prohibited_clauses:
        return 3.0  # Triple the score for prohibited clauses
    
    # Default: no jurisdictional enhancement
    return 1.0


def get_system_prompt_for_jurisdiction(jurisdiction: Jurisdiction) -> str:
    """
    Get the system prompt addendum for a jurisdiction.
    
    Args:
        jurisdiction: Active jurisdiction
        
    Returns:
        System prompt text to inject into LLM
    """
    profile = get_jurisdiction_profile(jurisdiction)
    return profile.system_prompt_addendum


def get_required_disclosures(jurisdiction: Jurisdiction) -> List[str]:
    """
    Get list of required disclosures for a jurisdiction.
    
    Args:
        jurisdiction: Active jurisdiction
        
    Returns:
        List of required disclosure descriptions
    """
    profile = get_jurisdiction_profile(jurisdiction)
    return profile.required_disclosures


def check_missing_disclosures(
    contract_text: str,
    jurisdiction: Jurisdiction
) -> List[str]:
    """
    Check which required disclosures are missing from contract.
    
    Args:
        contract_text: Full contract text
        jurisdiction: Active jurisdiction
        
    Returns:
        List of missing required disclosures
    """
    profile = get_jurisdiction_profile(jurisdiction)
    contract_lower = contract_text.lower()
    
    missing = []
    
    # Simple keyword-based detection (can be enhanced with NLP)
    for disclosure in profile.required_disclosures:
        # Extract key terms from disclosure
        if jurisdiction == Jurisdiction.CALIFORNIA:
            if "do not sell" in disclosure.lower() and "do not sell" not in contract_lower:
                missing.append(disclosure)
            elif "auto-renewal" in disclosure.lower() and "auto" not in contract_lower:
                missing.append(disclosure)
        
        elif jurisdiction == Jurisdiction.EUROPE:
            if "right to erasure" in disclosure.lower() and "erasure" not in contract_lower and "delete" not in contract_lower:
                missing.append(disclosure)
            elif "data portability" in disclosure.lower() and "portability" not in contract_lower:
                missing.append(disclosure)
    
    return missing


# ══════════════════════════════════════════════════════════════════════════════
# JURISDICTION COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def compare_jurisdictions() -> Dict[str, Dict[str, any]]:
    """
    Generate comparison table of all jurisdictions.
    
    Returns:
        Dict with jurisdiction comparison data
    """
    comparison = {}
    
    for jurisdiction, profile in JURISDICTION_REGISTRY.items():
        comparison[profile.display_name] = {
            "enhanced_rule_count": len(profile.enhanced_rules),
            "prohibited_clause_count": len(profile.prohibited_clauses),
            "required_disclosure_count": len(profile.required_disclosures),
            "max_penalty_usd": profile.max_penalty_per_violation,
            "key_focus": _get_key_focus(jurisdiction)
        }
    
    return comparison


def _get_key_focus(jurisdiction: Jurisdiction) -> str:
    """Get human-readable key focus area for jurisdiction"""
    if jurisdiction == Jurisdiction.FEDERAL:
        return "Consumer protection, telemarketing, unfair practices"
    elif jurisdiction == Jurisdiction.CALIFORNIA:
        return "Data privacy, auto-renewal, consumer rights"
    elif jurisdiction == Jurisdiction.EUROPE:
        return "Data protection, consent, cross-border transfers"
    return "Unknown"


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def format_max_penalty(jurisdiction: Jurisdiction) -> str:
    """Format maximum penalty for display"""
    profile = get_jurisdiction_profile(jurisdiction)
    penalty = profile.max_penalty_per_violation
    
    if penalty >= 1000000:
        return f"${penalty/1000000:.0f}M"
    elif penalty >= 1000:
        return f"${penalty/1000:.0f}K"
    else:
        return f"${penalty}"


def get_jurisdiction_summary(jurisdiction: Jurisdiction) -> str:
    """Get human-readable summary of jurisdiction"""
    profile = get_jurisdiction_profile(jurisdiction)
    
    return f"""
{profile.display_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enhanced Rules: {len(profile.enhanced_rules)}
Prohibited Clauses: {len(profile.prohibited_clauses) if profile.prohibited_clauses else 'None'}
Required Disclosures: {len(profile.required_disclosures)}
Max Penalty per Violation: {format_max_penalty(jurisdiction)}
    """.strip()
