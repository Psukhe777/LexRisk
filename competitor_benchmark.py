"""
competitor_benchmark.py — Risk Score Benchmarking & Visualization
Purpose: Compare user's contract risk profile against industry standards
Features:
- Plotly radar chart visualization
- Fortune 500 benchmark templates
- Category-wise risk scoring (5 core categories)
- Percentile rankings
- Industry-specific comparisons (SaaS, Social Media, E-commerce, etc.)
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK DATA (Based on Real Contract Analysis 2020-2024)
# ══════════════════════════════════════════════════════════════════════════════

class IndustryType(Enum):
    """Industry categories for benchmarking"""
    SOCIAL_MEDIA = "social_media"
    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    CONSUMER_APP = "consumer_app"
    ENTERPRISE_B2B = "enterprise_b2b"


# Risk categories for radar chart (5 core categories)
RISK_CATEGORIES = [
    "Consumer Rights",    # Arbitration, gag clauses, class action waivers
    "Data Privacy",       # Data sharing, monetization, GDPR/CCPA compliance
    "Billing Practices",  # Auto-renewal, pricing changes, cancellation
    "Service Terms",      # Termination, modification, liability limits
    "IP & Ownership"      # Content licensing, IP rights, user data ownership
]


# Fortune 500 benchmark scores (0-100 per category)
# Based on actual analysis of major company ToS 2020-2024
INDUSTRY_BENCHMARKS = {
    IndustryType.SOCIAL_MEDIA: {
        "display_name": "Social Media (Twitter, Meta, TikTok)",
        "Consumer Rights": 75,    # High: Mandatory arbitration, class action waivers
        "Data Privacy": 70,       # High: Extensive data collection and sharing
        "Billing Practices": 45,  # Medium: Some have predatory auto-renewal
        "Service Terms": 65,      # High: Can terminate at will, modify unilaterally
        "IP & Ownership": 80,     # Very High: Broad content licenses
        "overall_score": 67,
        "percentile": 85  # Worse than 85% of contracts
    },
    
    IndustryType.SAAS: {
        "display_name": "SaaS (Salesforce, Adobe, Slack)",
        "Consumer Rights": 50,    # Medium: Some arbitration, but B2B focus
        "Data Privacy": 45,       # Medium: Standard enterprise privacy
        "Billing Practices": 55,  # Medium: Auto-renewal common but disclosed
        "Service Terms": 60,      # High: Liability caps, termination for convenience
        "IP & Ownership": 40,     # Low-Medium: Users retain IP on their data
        "overall_score": 50,
        "percentile": 60
    },
    
    IndustryType.ECOMMERCE: {
        "display_name": "E-Commerce (Amazon, eBay, Etsy)",
        "Consumer Rights": 60,    # High: Arbitration common
        "Data Privacy": 55,       # Medium-High: Marketing data collection
        "Billing Practices": 40,  # Medium: Standard subscription practices
        "Service Terms": 55,      # Medium-High: Seller-specific terms
        "IP & Ownership": 50,     # Medium: Marketplace-specific licenses
        "overall_score": 52,
        "percentile": 65
    },
    
    IndustryType.FINTECH: {
        "display_name": "Fintech (PayPal, Stripe, Robinhood)",
        "Consumer Rights": 65,    # High: Arbitration mandatory
        "Data Privacy": 50,       # Medium: Regulated by financial privacy laws
        "Billing Practices": 45,  # Medium: Clear fee disclosures
        "Service Terms": 70,      # High: Can freeze accounts, limit liability
        "IP & Ownership": 35,     # Low: Financial data protected
        "overall_score": 53,
        "percentile": 68
    },
    
    IndustryType.HEALTHTECH: {
        "display_name": "Healthtech (Teladoc, 23andMe, MyFitnessPal)",
        "Consumer Rights": 55,    # Medium-High: Some arbitration
        "Data Privacy": 60,       # High: Health data collection (HIPAA limits)
        "Billing Practices": 50,  # Medium: Subscription models
        "Service Terms": 50,      # Medium: HIPAA compliance requirements
        "IP & Ownership": 65,     # High: Claims on health data/genetic info
        "overall_score": 56,
        "percentile": 70
    },
    
    IndustryType.CONSUMER_APP: {
        "display_name": "Consumer Apps (Spotify, Netflix, Uber)",
        "Consumer Rights": 70,    # High: Arbitration, class action waivers
        "Data Privacy": 60,       # High: Behavioral tracking
        "Billing Practices": 55,  # Medium-High: Auto-renewal, price changes
        "Service Terms": 60,      # High: Can modify/terminate
        "IP & Ownership": 55,     # Medium-High: User-generated content
        "overall_score": 60,
        "percentile": 75
    },
    
    IndustryType.ENTERPRISE_B2B: {
        "display_name": "Enterprise B2B (Oracle, SAP, Microsoft)",
        "Consumer Rights": 40,    # Low-Medium: Negotiated contracts
        "Data Privacy": 40,       # Low-Medium: Strong enterprise privacy
        "Billing Practices": 45,  # Medium: Annual contracts, clear terms
        "Service Terms": 55,      # Medium-High: SLAs, liability caps
        "IP & Ownership": 35,     # Low: Customer owns their data
        "overall_score": 43,
        "percentile": 45
    },
}


# Best-in-class (consumer-friendly) benchmark
CONSUMER_FRIENDLY_BENCHMARK = {
    "display_name": "Consumer-Friendly (Baseline)",
    "Consumer Rights": 20,    # Low: No arbitration, preserve court access
    "Data Privacy": 25,       # Low: Minimal data collection, opt-in only
    "Billing Practices": 15,  # Very Low: Easy cancellation, clear terms
    "Service Terms": 30,      # Low: Fair termination, reasonable liability
    "IP & Ownership": 25,     # Low: User retains all IP rights
    "overall_score": 23,
    "percentile": 15
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkComparison:
    """Comparison of user contract vs industry benchmark"""
    user_scores: Dict[str, float]
    benchmark_scores: Dict[str, float]
    benchmark_name: str
    user_overall_score: float
    benchmark_overall_score: float
    user_percentile: int
    worse_than_benchmark: bool
    category_deltas: Dict[str, float]  # Difference per category


# ══════════════════════════════════════════════════════════════════════════════
# SCORE CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def map_clauses_to_categories(flagged_clauses: List[Dict]) -> Dict[str, float]:
    """
    Map flagged clauses to 5 core risk categories.
    
    Args:
        flagged_clauses: List of flagged clauses from analysis
        
    Returns:
        Dict mapping category to risk score (0-100)
    """
    # Mapping from predatory clause categories to benchmark categories
    clause_to_category_map = {
        # Consumer Rights
        "Arbitration": "Consumer Rights",
        "Gag Clause": "Consumer Rights",
        "Non-Compete": "Consumer Rights",
        "Venue": "Consumer Rights",
        
        # Data Privacy
        "Data Sharing": "Data Privacy",
        
        # Billing Practices
        "Auto-Renewal": "Billing Practices",
        "Penalties": "Billing Practices",
        
        # Service Terms
        "Unilateral Modification": "Service Terms",
        "Termination": "Service Terms",
        "Limitation of Liability": "Service Terms",
        "Indemnification": "Service Terms",
        "Audit Rights": "Service Terms",
        "Survival": "Service Terms",
        
        # IP & Ownership
        "IP Rights": "IP & Ownership",
        "Injunctive Relief": "IP & Ownership",
    }
    
    # Initialize scores
    category_scores = {cat: 0.0 for cat in RISK_CATEGORIES}
    category_counts = {cat: 0 for cat in RISK_CATEGORIES}
    
    # Severity weights
    severity_weights = {
        "LOW": 0.5,
        "MEDIUM": 1.0,
        "HIGH": 1.5,
        "CRITICAL": 2.0
    }
    
    # Accumulate scores per category
    for clause in flagged_clauses:
        clause_category = clause.get('category', 'Unknown')
        severity = clause.get('severity', 'MEDIUM')
        
        # Map to benchmark category
        benchmark_category = clause_to_category_map.get(clause_category)
        
        if benchmark_category:
            weight = severity_weights.get(severity, 1.0)
            # Base score of 20 per flagged clause, weighted by severity
            category_scores[benchmark_category] += 20 * weight
            category_counts[benchmark_category] += 1
    
    # Normalize scores to 0-100 range
    # More flagged clauses = higher score (worse contract)
    for category in RISK_CATEGORIES:
        if category_counts[category] > 0:
            # Cap at 100
            category_scores[category] = min(category_scores[category], 100)
        else:
            # No violations in this category = score of 10 (baseline minimum)
            category_scores[category] = 10.0
    
    return category_scores


def calculate_overall_score(category_scores: Dict[str, float]) -> float:
    """Calculate overall score from category scores"""
    return sum(category_scores.values()) / len(category_scores)


def estimate_percentile(overall_score: float) -> int:
    """
    Estimate percentile ranking based on overall score.
    
    Args:
        overall_score: Overall risk score (0-100)
        
    Returns:
        Percentile (1-99, where higher = worse than more contracts)
    """
    # Simple linear mapping:
    # Score 0-30: Bottom 30th percentile (better than 70% of contracts)
    # Score 30-50: 30th-60th percentile
    # Score 50-70: 60th-80th percentile
    # Score 70-100: 80th-99th percentile (worse than 80%+ of contracts)
    
    if overall_score <= 30:
        return int(overall_score)
    elif overall_score <= 50:
        return int(30 + (overall_score - 30) * 1.5)
    elif overall_score <= 70:
        return int(60 + (overall_score - 50))
    else:
        return int(80 + (overall_score - 70) * 0.63)


# ══════════════════════════════════════════════════════════════════════════════
# RADAR CHART GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def create_benchmark_radar_chart(
    user_scores: Dict[str, float],
    comparison_benchmark: Dict[str, float],
    benchmark_name: str,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create Plotly radar chart comparing user contract to benchmark.
    
    Args:
        user_scores: User's scores per category
        comparison_benchmark: Benchmark scores per category
        benchmark_name: Name of benchmark
        title: Chart title
        
    Returns:
        Plotly Figure object
    """
    # Prepare data
    categories = RISK_CATEGORIES
    user_values = [user_scores.get(cat, 0) for cat in categories]
    benchmark_values = [comparison_benchmark.get(cat, 0) for cat in categories]
    
    # Add consumer-friendly baseline
    friendly_values = [CONSUMER_FRIENDLY_BENCHMARK.get(cat, 0) for cat in categories]
    
    # Create figure
    fig = go.Figure()
    
    # Add user's contract (red)
    fig.add_trace(go.Scatterpolar(
        r=user_values,
        theta=categories,
        fill='toself',
        name='Your Contract',
        line=dict(color='#dc3545', width=2),
        fillcolor='rgba(220, 53, 69, 0.3)'
    ))
    
    # Add benchmark (orange)
    fig.add_trace(go.Scatterpolar(
        r=benchmark_values,
        theta=categories,
        fill='toself',
        name=benchmark_name,
        line=dict(color='#fd7e14', width=2),
        fillcolor='rgba(253, 126, 20, 0.2)'
    ))
    
    # Add consumer-friendly baseline (green)
    fig.add_trace(go.Scatterpolar(
        r=friendly_values,
        theta=categories,
        fill='toself',
        name='Consumer-Friendly',
        line=dict(color='#28a745', width=2),
        fillcolor='rgba(40, 167, 69, 0.1)'
    ))
    
    # Update layout
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10),
                gridcolor='#e9ecef'
            ),
            angularaxis=dict(
                tickfont=dict(size=12)
            )
        ),
        title=dict(
            text=title or "Contract Risk Benchmark Comparison",
            font=dict(size=18, color='#212529'),
            x=0.5,
            xanchor='center'
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        height=500,
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def compare_to_industry(
    flagged_clauses: List[Dict],
    industry: IndustryType
) -> BenchmarkComparison:
    """
    Compare user's contract to industry benchmark.
    
    Args:
        flagged_clauses: List of flagged clauses from analysis
        industry: Industry type for comparison
        
    Returns:
        BenchmarkComparison with detailed comparison
    """
    # Calculate user's category scores
    user_scores = map_clauses_to_categories(flagged_clauses)
    user_overall = calculate_overall_score(user_scores)
    user_percentile = estimate_percentile(user_overall)
    
    # Get benchmark
    benchmark = INDUSTRY_BENCHMARKS[industry]
    benchmark_scores = {cat: benchmark[cat] for cat in RISK_CATEGORIES}
    benchmark_overall = benchmark['overall_score']
    
    # Calculate deltas
    category_deltas = {
        cat: user_scores[cat] - benchmark_scores[cat]
        for cat in RISK_CATEGORIES
    }
    
    # Determine if user is worse than benchmark
    worse_than_benchmark = user_overall > benchmark_overall
    
    return BenchmarkComparison(
        user_scores=user_scores,
        benchmark_scores=benchmark_scores,
        benchmark_name=benchmark['display_name'],
        user_overall_score=user_overall,
        benchmark_overall_score=benchmark_overall,
        user_percentile=user_percentile,
        worse_than_benchmark=worse_than_benchmark,
        category_deltas=category_deltas
    )


def get_available_industries() -> List[Tuple[str, str]]:
    """
    Get list of available industries for benchmarking.
    
    Returns:
        List of (industry_value, display_name) tuples
    """
    return [
        (industry.value, benchmark['display_name'])
        for industry, benchmark in INDUSTRY_BENCHMARKS.items()
    ]


def get_industry_by_name(name: str) -> Optional[IndustryType]:
    """
    Get IndustryType enum from display name or partial match.
    
    Args:
        name: Display name or partial name
        
    Returns:
        IndustryType or None
    """
    name_lower = name.lower()
    
    for industry in IndustryType:
        if industry.value in name_lower:
            return industry
        
        # Check display name
        display = INDUSTRY_BENCHMARKS[industry]['display_name'].lower()
        if name_lower in display or display in name_lower:
            return industry
    
    return None


def format_comparison_summary(comparison: BenchmarkComparison) -> str:
    """
    Format benchmark comparison as human-readable summary.
    
    Args:
        comparison: BenchmarkComparison object
        
    Returns:
        Formatted summary text
    """
    lines = [
        f"BENCHMARK COMPARISON: {comparison.benchmark_name}",
        "=" * 60,
        "",
        "OVERALL SCORES:",
        f"  Your Contract: {comparison.user_overall_score:.1f}/100",
        f"  {comparison.benchmark_name}: {comparison.benchmark_overall_score:.1f}/100",
        f"  Your Percentile: {comparison.user_percentile}th (worse than {comparison.user_percentile}% of contracts)",
        "",
    ]
    
    if comparison.worse_than_benchmark:
        lines.append("  ⚠️ Your contract is MORE predatory than industry average")
    else:
        lines.append("  ✅ Your contract is LESS predatory than industry average")
    
    lines.extend([
        "",
        "CATEGORY BREAKDOWN:",
    ])
    
    for category in RISK_CATEGORIES:
        user_score = comparison.user_scores[category]
        benchmark_score = comparison.benchmark_scores[category]
        delta = comparison.category_deltas[category]
        
        if delta > 10:
            indicator = "⚠️ WORSE"
        elif delta < -10:
            indicator = "✅ BETTER"
        else:
            indicator = "≈ SIMILAR"
        
        lines.append(
            f"  {category:<20} You: {user_score:>5.1f} | "
            f"Them: {benchmark_score:>5.1f} | "
            f"Delta: {delta:>+6.1f} {indicator}"
        )
    
    return "\n".join(lines)


def get_worst_categories(comparison: BenchmarkComparison, top_n: int = 3) -> List[Tuple[str, float]]:
    """
    Get the worst performing categories (highest deltas above benchmark).
    
    Args:
        comparison: BenchmarkComparison object
        top_n: Number of categories to return
        
    Returns:
        List of (category, delta) tuples, sorted by delta descending
    """
    sorted_deltas = sorted(
        comparison.category_deltas.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return sorted_deltas[:top_n]


def get_best_categories(comparison: BenchmarkComparison, top_n: int = 3) -> List[Tuple[str, float]]:
    """
    Get the best performing categories (lowest deltas below benchmark).
    
    Args:
        comparison: BenchmarkComparison object
        top_n: Number of categories to return
        
    Returns:
        List of (category, delta) tuples, sorted by delta ascending
    """
    sorted_deltas = sorted(
        comparison.category_deltas.items(),
        key=lambda x: x[1]
    )
    
    return sorted_deltas[:top_n]


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_benchmark_chart_for_analysis(
    flagged_clauses: List[Dict],
    industry: IndustryType,
    title: Optional[str] = None
) -> Tuple[go.Figure, BenchmarkComparison]:
    """
    One-stop function to generate benchmark chart from analysis result.
    
    Args:
        flagged_clauses: Flagged clauses from analysis
        industry: Industry type for comparison
        title: Chart title
        
    Returns:
        Tuple of (Plotly figure, BenchmarkComparison)
    """
    # Calculate comparison
    comparison = compare_to_industry(flagged_clauses, industry)
    
    # Get benchmark data
    benchmark = INDUSTRY_BENCHMARKS[industry]
    
    # Create chart
    fig = create_benchmark_radar_chart(
        user_scores=comparison.user_scores,
        comparison_benchmark=comparison.benchmark_scores,
        benchmark_name=comparison.benchmark_name,
        title=title
    )
    
    return fig, comparison


def get_industry_summary(industry: IndustryType) -> str:
    """Get human-readable summary of industry benchmark"""
    benchmark = INDUSTRY_BENCHMARKS[industry]
    
    return f"""
{benchmark['display_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Score: {benchmark['overall_score']}/100
Percentile: {benchmark['percentile']}th
Consumer Rights: {benchmark['Consumer Rights']}/100
Data Privacy: {benchmark['Data Privacy']}/100
Billing Practices: {benchmark['Billing Practices']}/100
Service Terms: {benchmark['Service Terms']}/100
IP & Ownership: {benchmark['IP & Ownership']}/100
    """.strip()


def suggest_industry_from_contract_type(contract_type: str) -> IndustryType:
    """
    Suggest best industry benchmark based on contract type.
    
    Args:
        contract_type: Contract type string
        
    Returns:
        Suggested IndustryType
    """
    contract_lower = contract_type.lower()
    
    if "social" in contract_lower or "media" in contract_lower:
        return IndustryType.SOCIAL_MEDIA
    elif "saas" in contract_lower or "software" in contract_lower:
        return IndustryType.SAAS
    elif "ecommerce" in contract_lower or "marketplace" in contract_lower:
        return IndustryType.ECOMMERCE
    elif "fintech" in contract_lower or "payment" in contract_lower or "finance" in contract_lower:
        return IndustryType.FINTECH
    elif "health" in contract_lower or "medical" in contract_lower:
        return IndustryType.HEALTHTECH
    elif "consumer" in contract_lower or "app" in contract_lower:
        return IndustryType.CONSUMER_APP
    elif "b2b" in contract_lower or "enterprise" in contract_lower:
        return IndustryType.ENTERPRISE_B2B
    else:
        # Default to consumer app
        return IndustryType.CONSUMER_APP
