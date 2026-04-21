"""
liability_calculator.py — Deterministic Lawsuit Liability Calculator
Purpose: Calculate potential financial liability for contract violations
Features:
- Per-violation penalty calculation (TCPA, GDPR, CCPA, FTC)
- Volume-based escalation (bulk violations increase per-unit penalty)
- Contract type risk adjustments (B2B vs consumer)
- Statutory vs actual damages estimation
- Attorney fees and litigation cost modeling
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from jurisdictional_rules import Jurisdiction, get_jurisdiction_profile

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PENALTY CONSTANTS (Based on 2024-2026 Statutory Maximums)
# ══════════════════════════════════════════════════════════════════════════════

# TCPA (Telephone Consumer Protection Act)
TCPA_PER_VIOLATION = 500  # Non-willful
TCPA_PER_VIOLATION_WILLFUL = 1500  # Willful/knowing

# GDPR (General Data Protection Regulation)
GDPR_TIER_1_MAX = 10000000  # €10M or 2% revenue (technical violations)
GDPR_TIER_2_MAX = 20000000  # €20M or 4% revenue (serious violations)
GDPR_MIN_PER_VIOLATION = 1000  # Practical minimum per violation

# CCPA/CPRA (California Consumer Privacy Act)
CCPA_PER_VIOLATION = 2500  # Non-intentional
CCPA_PER_VIOLATION_INTENTIONAL = 7500  # Intentional
CCPA_DATA_BREACH_PER_CONSUMER = 750  # Per affected consumer (statutory)

# FTC Act (Federal Trade Commission)
FTC_PER_VIOLATION = 50280  # 2024 adjusted maximum per violation

# Class Action Multipliers
CLASS_ACTION_MINIMUM_MEMBERS = 100  # Typical class certification threshold
CLASS_ACTION_AVERAGE_RECOVERY = 250  # Per class member (conservative estimate)

# Attorney Fees & Litigation Costs
ATTORNEY_FEES_PERCENTAGE = 0.33  # 33% contingency (standard)
LITIGATION_COSTS_BASE = 50000  # Discovery, experts, filing fees
LITIGATION_COSTS_PER_CLAIM = 10000  # Additional per substantive claim


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

class ViolationType(Enum):
    """Types of statutory violations"""
    TCPA_VIOLATION = "tcpa"
    GDPR_VIOLATION = "gdpr"
    CCPA_VIOLATION = "ccpa"
    FTC_UNFAIR_PRACTICE = "ftc"
    CONSUMER_FRAUD = "fraud"
    BREACH_OF_CONTRACT = "contract"


@dataclass
class ViolationEstimate:
    """Single violation cost estimate"""
    violation_type: ViolationType
    category: str  # Predatory clause category
    min_penalty: int
    max_penalty: int
    expected_penalty: int
    basis: str  # Explanation of calculation


@dataclass
class LiabilityReport:
    """Complete liability analysis"""
    jurisdiction: Jurisdiction
    contract_type: str
    total_violations: int
    
    # Penalty calculations
    statutory_penalties_min: int
    statutory_penalties_max: int
    statutory_penalties_expected: int
    
    # Class action estimates (if applicable)
    class_action_applicable: bool
    estimated_class_size: int
    class_action_total: int
    
    # Litigation costs
    attorney_fees: int
    litigation_costs: int
    
    # Grand total
    total_liability_min: int
    total_liability_max: int
    total_liability_expected: int
    
    # Breakdown by violation type
    violation_breakdown: List[ViolationEstimate]
    
    # Risk factors
    risk_multipliers: Dict[str, float]
    warnings: List[str]


# ══════════════════════════════════════════════════════════════════════════════
# VIOLATION MAPPING
# ══════════════════════════════════════════════════════════════════════════════

# Map predatory clause categories to statutory violation types
CATEGORY_TO_VIOLATION_TYPE = {
    # Data & Privacy violations
    "Data Sharing": {
        Jurisdiction.FEDERAL: ViolationType.TCPA_VIOLATION,
        Jurisdiction.CALIFORNIA: ViolationType.CCPA_VIOLATION,
        Jurisdiction.EUROPE: ViolationType.GDPR_VIOLATION,
    },
    
    # Consumer protection violations
    "Gag Clause": {
        Jurisdiction.FEDERAL: ViolationType.FTC_UNFAIR_PRACTICE,
        Jurisdiction.CALIFORNIA: ViolationType.CONSUMER_FRAUD,
        Jurisdiction.EUROPE: ViolationType.GDPR_VIOLATION,  # If data-related
    },
    
    "Auto-Renewal": {
        Jurisdiction.FEDERAL: ViolationType.FTC_UNFAIR_PRACTICE,
        Jurisdiction.CALIFORNIA: ViolationType.CONSUMER_FRAUD,
        Jurisdiction.EUROPE: ViolationType.CONSUMER_FRAUD,
    },
    
    "Unilateral Modification": {
        Jurisdiction.FEDERAL: ViolationType.FTC_UNFAIR_PRACTICE,
        Jurisdiction.CALIFORNIA: ViolationType.CONSUMER_FRAUD,
        Jurisdiction.EUROPE: ViolationType.CONSUMER_FRAUD,
    },
    
    # Contract law violations (generally state law, not statutory)
    "Limitation of Liability": {
        Jurisdiction.FEDERAL: ViolationType.BREACH_OF_CONTRACT,
        Jurisdiction.CALIFORNIA: ViolationType.BREACH_OF_CONTRACT,
        Jurisdiction.EUROPE: ViolationType.BREACH_OF_CONTRACT,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# CORE CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

class LiabilityCalculator:
    """
    Deterministic calculator for lawsuit liability estimation.
    """
    
    def __init__(self, jurisdiction: Jurisdiction):
        """
        Initialize calculator for specific jurisdiction.
        
        Args:
            jurisdiction: Legal jurisdiction for calculations
        """
        self.jurisdiction = jurisdiction
        self.profile = get_jurisdiction_profile(jurisdiction)
        logger.info(f"LiabilityCalculator initialized for {self.profile.display_name}")
    
    def calculate_liability(
        self,
        flagged_clauses: List[Dict],
        contract_type: str = "consumer",
        estimated_affected_users: int = 1000
    ) -> LiabilityReport:
        """
        Calculate total potential liability for flagged clauses.
        
        Args:
            flagged_clauses: List of flagged clauses (from AnalysisResult)
            contract_type: "consumer", "b2b", "employment", etc.
            estimated_affected_users: Number of potentially affected users
            
        Returns:
            LiabilityReport with detailed calculations
        """
        violation_estimates = []
        total_min = 0
        total_max = 0
        total_expected = 0
        
        # Calculate per-violation penalties
        for clause in flagged_clauses:
            category = clause.get('category', 'Unknown')
            severity = clause.get('severity', 'MEDIUM')
            
            # Get violation type for this category and jurisdiction
            violation_type = self._get_violation_type(category)
            
            # Calculate penalty for this violation
            estimate = self._calculate_single_violation(
                violation_type,
                category,
                severity,
                estimated_affected_users
            )
            
            violation_estimates.append(estimate)
            total_min += estimate.min_penalty
            total_max += estimate.max_penalty
            total_expected += estimate.expected_penalty
        
        # Class action analysis
        class_action_applicable = self._is_class_action_viable(
            contract_type,
            len(flagged_clauses),
            estimated_affected_users
        )
        
        if class_action_applicable:
            estimated_class_size = max(estimated_affected_users, CLASS_ACTION_MINIMUM_MEMBERS)
            class_action_total = estimated_class_size * CLASS_ACTION_AVERAGE_RECOVERY
        else:
            estimated_class_size = 0
            class_action_total = 0
        
        # Litigation costs
        attorney_fees = int((total_expected + class_action_total) * ATTORNEY_FEES_PERCENTAGE)
        litigation_costs = LITIGATION_COSTS_BASE + (len(flagged_clauses) * LITIGATION_COSTS_PER_CLAIM)
        
        # Risk multipliers
        risk_multipliers = self._calculate_risk_multipliers(
            contract_type,
            len(flagged_clauses),
            estimated_affected_users
        )
        
        # Apply multipliers to expected value
        for multiplier_name, multiplier_value in risk_multipliers.items():
            total_expected = int(total_expected * multiplier_value)
        
        # Warnings
        warnings = self._generate_warnings(
            flagged_clauses,
            contract_type,
            estimated_affected_users
        )
        
        # Build report
        report = LiabilityReport(
            jurisdiction=self.jurisdiction,
            contract_type=contract_type,
            total_violations=len(flagged_clauses),
            statutory_penalties_min=total_min,
            statutory_penalties_max=total_max,
            statutory_penalties_expected=total_expected,
            class_action_applicable=class_action_applicable,
            estimated_class_size=estimated_class_size,
            class_action_total=class_action_total,
            attorney_fees=attorney_fees,
            litigation_costs=litigation_costs,
            total_liability_min=total_min + litigation_costs,
            total_liability_max=total_max + class_action_total + attorney_fees + litigation_costs,
            total_liability_expected=total_expected + class_action_total + attorney_fees + litigation_costs,
            violation_breakdown=violation_estimates,
            risk_multipliers=risk_multipliers,
            warnings=warnings
        )
        
        logger.info(
            f"Liability calculated: ${report.total_liability_expected:,} expected "
            f"(range: ${report.total_liability_min:,} - ${report.total_liability_max:,})"
        )
        
        return report
    
    def _get_violation_type(self, category: str) -> ViolationType:
        """Determine violation type based on category and jurisdiction"""
        if category in CATEGORY_TO_VIOLATION_TYPE:
            jurisdiction_map = CATEGORY_TO_VIOLATION_TYPE[category]
            return jurisdiction_map.get(self.jurisdiction, ViolationType.BREACH_OF_CONTRACT)
        
        # Default fallback
        return ViolationType.BREACH_OF_CONTRACT
    
    def _calculate_single_violation(
        self,
        violation_type: ViolationType,
        category: str,
        severity: str,
        affected_users: int
    ) -> ViolationEstimate:
        """Calculate penalty for a single violation"""
        
        # Severity multiplier
        severity_multiplier = {
            "LOW": 0.5,
            "MEDIUM": 1.0,
            "HIGH": 1.5,
            "CRITICAL": 2.0
        }.get(severity, 1.0)
        
        # Calculate based on violation type
        if violation_type == ViolationType.TCPA_VIOLATION:
            min_penalty = TCPA_PER_VIOLATION * affected_users
            max_penalty = TCPA_PER_VIOLATION_WILLFUL * affected_users
            expected_penalty = int(((min_penalty + max_penalty) / 2) * severity_multiplier)
            basis = f"TCPA: ${TCPA_PER_VIOLATION}-${TCPA_PER_VIOLATION_WILLFUL} per violation × {affected_users} users"
        
        elif violation_type == ViolationType.GDPR_VIOLATION:
            # GDPR penalties are per-incident, not per-user
            min_penalty = GDPR_MIN_PER_VIOLATION
            max_penalty = min(GDPR_TIER_2_MAX, affected_users * 100)  # Cap at tier 2 max
            expected_penalty = int(min(GDPR_TIER_2_MAX * 0.1, affected_users * 50) * severity_multiplier)
            basis = f"GDPR: Up to €20M per violation (estimated based on {affected_users} affected users)"
        
        elif violation_type == ViolationType.CCPA_VIOLATION:
            min_penalty = CCPA_PER_VIOLATION * affected_users
            max_penalty = CCPA_PER_VIOLATION_INTENTIONAL * affected_users
            expected_penalty = int(((min_penalty + max_penalty) / 2) * severity_multiplier)
            basis = f"CCPA: ${CCPA_PER_VIOLATION}-${CCPA_PER_VIOLATION_INTENTIONAL} per violation × {affected_users} users"
        
        elif violation_type == ViolationType.FTC_UNFAIR_PRACTICE:
            min_penalty = FTC_PER_VIOLATION
            max_penalty = FTC_PER_VIOLATION * min(affected_users, 100)  # Cap at 100 violations
            expected_penalty = int((FTC_PER_VIOLATION * min(affected_users / 10, 10)) * severity_multiplier)
            basis = f"FTC Act: Up to ${FTC_PER_VIOLATION:,} per violation"
        
        elif violation_type == ViolationType.CONSUMER_FRAUD:
            # State-level consumer fraud (varies by state)
            min_penalty = 1000 * affected_users
            max_penalty = 5000 * affected_users
            expected_penalty = int(((min_penalty + max_penalty) / 2) * severity_multiplier)
            basis = f"Consumer fraud: Estimated $1,000-$5,000 per affected consumer"
        
        else:  # BREACH_OF_CONTRACT
            # Contract damages: harder to quantify, use conservative estimate
            min_penalty = 500 * affected_users
            max_penalty = 2000 * affected_users
            expected_penalty = int(1000 * affected_users * severity_multiplier)
            basis = f"Contract damages: Estimated $500-$2,000 per affected party"
        
        return ViolationEstimate(
            violation_type=violation_type,
            category=category,
            min_penalty=min_penalty,
            max_penalty=max_penalty,
            expected_penalty=expected_penalty,
            basis=basis
        )
    
    def _is_class_action_viable(
        self,
        contract_type: str,
        violation_count: int,
        affected_users: int
    ) -> bool:
        """Determine if class action is viable"""
        # Class action typically requires:
        # 1. Minimum number of affected parties (usually 40-100)
        # 2. Common questions of law/fact
        # 3. Consumer contracts (not B2B)
        
        if contract_type.lower() == "b2b":
            return False  # B2B disputes rarely certify as class actions
        
        if affected_users < CLASS_ACTION_MINIMUM_MEMBERS:
            return False
        
        if violation_count < 2:
            return False  # Need pattern of violations
        
        return True
    
    def _calculate_risk_multipliers(
        self,
        contract_type: str,
        violation_count: int,
        affected_users: int
    ) -> Dict[str, float]:
        """Calculate risk multipliers based on context"""
        multipliers = {}
        
        # Volume multiplier (more violations = higher scrutiny)
        if violation_count >= 10:
            multipliers['high_violation_count'] = 1.5
        elif violation_count >= 5:
            multipliers['moderate_violation_count'] = 1.2
        
        # Scale multiplier (more affected users = higher damages)
        if affected_users >= 10000:
            multipliers['large_scale'] = 1.8
        elif affected_users >= 1000:
            multipliers['medium_scale'] = 1.3
        
        # Contract type adjustment
        if contract_type.lower() == "employment":
            multipliers['employment_context'] = 1.4  # Higher scrutiny
        elif contract_type.lower() == "b2b":
            multipliers['b2b_discount'] = 0.7  # Lower statutory penalties
        
        return multipliers
    
    def _generate_warnings(
        self,
        flagged_clauses: List[Dict],
        contract_type: str,
        affected_users: int
    ) -> List[str]:
        """Generate specific warnings about liability exposure"""
        warnings = []
        
        # Check for CRITICAL severity violations
        critical_count = sum(1 for c in flagged_clauses if c.get('severity') == 'CRITICAL')
        if critical_count >= 3:
            warnings.append(
                f"⚠️ {critical_count} CRITICAL violations detected. "
                f"Risk of regulatory investigation and injunctive relief."
            )
        
        # Check for data-related violations (high penalty risk)
        data_violations = [c for c in flagged_clauses if 'data' in c.get('category', '').lower()]
        if data_violations and self.jurisdiction in [Jurisdiction.CALIFORNIA, Jurisdiction.EUROPE]:
            warnings.append(
                "⚠️ Data privacy violations carry severe penalties in this jurisdiction. "
                "Consider immediate remediation."
            )
        
        # Check for gag clauses (often illegal)
        gag_clauses = [c for c in flagged_clauses if 'gag' in c.get('category', '').lower()]
        if gag_clauses:
            warnings.append(
                "⚠️ Non-disparagement clauses may be void under Consumer Review Fairness Act. "
                "Remove to avoid FTC enforcement."
            )
        
        # Large scale warning
        if affected_users >= 10000:
            warnings.append(
                f"⚠️ Large-scale exposure ({affected_users:,} users). "
                f"Class action certification likely if sued."
            )
        
        return warnings


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_liability_for_analysis(
    flagged_clauses: List[Dict],
    jurisdiction: Jurisdiction,
    contract_type: str = "consumer",
    estimated_users: int = 1000
) -> LiabilityReport:
    """
    Convenience function to calculate liability from analysis result.
    
    Args:
        flagged_clauses: List of flagged clauses from AnalysisResult
        jurisdiction: Legal jurisdiction
        contract_type: Type of contract
        estimated_users: Estimated affected user count
        
    Returns:
        LiabilityReport
    """
    calculator = LiabilityCalculator(jurisdiction)
    return calculator.calculate_liability(flagged_clauses, contract_type, estimated_users)


def format_liability_summary(report: LiabilityReport) -> str:
    """Format liability report as human-readable summary"""
    lines = [
        f"POTENTIAL LIABILITY ANALYSIS ({report.jurisdiction.value.upper()})",
        "=" * 60,
        f"Contract Type: {report.contract_type.title()}",
        f"Total Violations: {report.total_violations}",
        "",
        "ESTIMATED LIABILITY:",
        f"  Statutory Penalties: ${report.statutory_penalties_expected:,}",
    ]
    
    if report.class_action_applicable:
        lines.extend([
            f"  Class Action Damages: ${report.class_action_total:,}",
            f"    (Estimated class size: {report.estimated_class_size:,} members)",
        ])
    
    lines.extend([
        f"  Attorney Fees: ${report.attorney_fees:,}",
        f"  Litigation Costs: ${report.litigation_costs:,}",
        "",
        f"TOTAL EXPECTED LIABILITY: ${report.total_liability_expected:,}",
        f"  Range: ${report.total_liability_min:,} - ${report.total_liability_max:,}",
    ])
    
    if report.warnings:
        lines.extend(["", "WARNINGS:"])
        for warning in report.warnings:
            lines.append(f"  {warning}")
    
    return "\n".join(lines)
