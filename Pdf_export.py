"""
pdf_export.py — Litigation Shield PDF Export
Purpose: Generate professional PDF reports for legal proceedings
Features:
- ReportLab PDF generation with professional formatting
- Cover page with branding
- Executive summary
- Redlined flagged clauses
- Liability calculations
- Legal citations and recommendations
- Timestamped audit trail
"""

import logging
import io
from typing import Dict, List, Optional
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image as RLImage
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

PAGE_SIZE = letter
MARGIN = 0.75 * inch
TITLE_COLOR = colors.HexColor('#667eea')
CRITICAL_COLOR = colors.HexColor('#dc3545')
HIGH_COLOR = colors.HexColor('#fd7e14')
MEDIUM_COLOR = colors.HexColor('#ffc107')
LOW_COLOR = colors.HexColor('#28a745')


# ══════════════════════════════════════════════════════════════════════════════
# PDF GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class LitigationShieldPDF:
    """
    Professional PDF report generator for legal proceedings.
    """
    
    def __init__(self):
        """Initialize PDF generator"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is required for PDF export. "
                "Install with: pip install reportlab"
            )
        
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        logger.info("✅ PDF generator initialized")
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=TITLE_COLOR,
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#6c757d'),
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=TITLE_COLOR,
            spaceAfter=12,
            spaceBefore=20
        ))
        
        # Warning text
        self.styles.add(ParagraphStyle(
            name='WarningText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=CRITICAL_COLOR,
            leftIndent=20,
            rightIndent=20
        ))
        
        # Clause text
        self.styles.add(ParagraphStyle(
            name='ClauseText',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=10,
            rightIndent=10,
            alignment=TA_JUSTIFY
        ))
    
    def generate_report(
        self,
        analysis_result: Dict,
        contract_name: str = "Untitled Contract",
        client_name: Optional[str] = None,
        include_liability: bool = True
    ) -> bytes:
        """
        Generate complete litigation shield PDF.
        
        Args:
            analysis_result: Analysis result dictionary
            contract_name: Name of contract
            client_name: Optional client name
            include_liability: Include liability calculations
            
        Returns:
            PDF bytes
        """
        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=PAGE_SIZE,
            rightMargin=MARGIN,
            leftMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN
        )
        
        # Build content
        story = []
        
        # Cover page
        story.extend(self._create_cover_page(contract_name, client_name, analysis_result))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._create_executive_summary(analysis_result))
        story.append(PageBreak())
        
        # Risk assessment
        story.extend(self._create_risk_assessment(analysis_result))
        story.append(PageBreak())
        
        # Flagged clauses
        story.extend(self._create_flagged_clauses_section(analysis_result))
        
        # Liability calculations
        if include_liability and 'liability_report' in analysis_result:
            story.append(PageBreak())
            story.extend(self._create_liability_section(analysis_result))
        
        # Recommendations
        story.append(PageBreak())
        story.extend(self._create_recommendations(analysis_result))
        
        # Legal disclaimer
        story.append(PageBreak())
        story.extend(self._create_disclaimer())
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"✅ Generated PDF report: {len(pdf_bytes):,} bytes")
        
        return pdf_bytes
    
    def _create_cover_page(
        self,
        contract_name: str,
        client_name: Optional[str],
        analysis_result: Dict
    ) -> List:
        """Create cover page"""
        story = []
        
        # Spacer for vertical centering
        story.append(Spacer(1, 2*inch))
        
        # Title
        title = Paragraph(
            "⚖️ LITIGATION SHIELD REPORT",
            self.styles['CustomTitle']
        )
        story.append(title)
        story.append(Spacer(1, 0.3*inch))
        
        # Contract name
        contract_title = Paragraph(
            f"<b>{contract_name}</b>",
            self.styles['CustomSubtitle']
        )
        story.append(contract_title)
        story.append(Spacer(1, 0.5*inch))
        
        # Risk badge
        risk_level = analysis_result.get('risk_level', 'UNKNOWN')
        risk_score = analysis_result.get('risk_score', 0)
        
        risk_colors_map = {
            'CRITICAL': CRITICAL_COLOR,
            'HIGH': HIGH_COLOR,
            'MEDIUM': MEDIUM_COLOR,
            'LOW': LOW_COLOR
        }
        
        risk_color = risk_colors_map.get(risk_level, colors.grey)
        
        risk_data = [[f"{risk_score}/100", risk_level]]
        risk_table = Table(risk_data, colWidths=[1.5*inch, 2*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), risk_color),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
            ('ALIGN', (0, 0), (1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 24),
            ('FONTSIZE', (1, 0), (1, 0), 16),
            ('PADDING', (0, 0), (1, 0), 12),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 0.5*inch))
        
        # Metadata table
        metadata = []
        
        if client_name:
            metadata.append(["Client:", client_name])
        
        metadata.extend([
            ["Analysis Date:", datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")],
            ["Jurisdiction:", str(analysis_result.get('jurisdiction', 'Federal'))],
            ["Flagged Clauses:", str(len(analysis_result.get('flagged_clauses', [])))],
            ["Report ID:", f"LR-{datetime.now().strftime('%Y%m%d-%H%M%S')}"]
        ])
        
        metadata_table = Table(metadata, colWidths=[1.5*inch, 3*inch])
        metadata_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(metadata_table)
        
        # Footer
        story.append(Spacer(1, 1*inch))
        footer = Paragraph(
            "<i>Powered by LexRisk AI-Powered Contract Analysis</i>",
            self.styles['CustomSubtitle']
        )
        story.append(footer)
        
        return story
    
    def _create_executive_summary(self, analysis_result: Dict) -> List:
        """Create executive summary section"""
        story = []
        
        story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        summary_text = analysis_result.get('summary', 'No summary available.')
        summary = Paragraph(summary_text, self.styles['Normal'])
        story.append(summary)
        
        story.append(Spacer(1, 0.3*inch))
        
        # Key findings
        story.append(Paragraph("Key Findings:", self.styles['Heading3']))
        
        flagged_clauses = analysis_result.get('flagged_clauses', [])
        
        # Count by severity
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for clause in flagged_clauses:
            severity = clause.get('severity', 'MEDIUM')
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        findings_data = [
            ["Severity", "Count"],
            ["CRITICAL", str(severity_counts['CRITICAL'])],
            ["HIGH", str(severity_counts['HIGH'])],
            ["MEDIUM", str(severity_counts['MEDIUM'])],
            ["LOW", str(severity_counts['LOW'])],
        ]
        
        findings_table = Table(findings_data, colWidths=[2*inch, 1.5*inch])
        findings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TITLE_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(findings_table)
        
        return story
    
    def _create_risk_assessment(self, analysis_result: Dict) -> List:
        """Create risk assessment section"""
        story = []
        
        story.append(Paragraph("RISK ASSESSMENT", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        # Risk matrix
        risk_score = analysis_result.get('risk_score', 0)
        risk_level = analysis_result.get('risk_level', 'UNKNOWN')
        
        assessment_text = f"""
        This contract has been assessed with a risk score of <b>{risk_score}/100</b>, 
        classified as <b>{risk_level} RISK</b>. This assessment is based on the presence 
        and severity of predatory clauses that may disadvantage consumers and violate 
        consumer protection laws.
        """
        
        story.append(Paragraph(assessment_text, self.styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Risk interpretation
        interpretation = {
            'CRITICAL': "Immediate legal review required. Multiple severe violations detected that likely violate consumer protection laws. High litigation risk.",
            'HIGH': "Significant concerns identified. Contract contains multiple predatory clauses that may be unenforceable. Legal review recommended.",
            'MEDIUM': "Moderate risk. Some concerning clauses present. Review recommended to assess enforceability.",
            'LOW': "Minimal concerns. Contract appears generally fair with only minor issues."
        }
        
        interp_text = interpretation.get(risk_level, "Risk level unknown.")
        story.append(Paragraph(f"<b>Interpretation:</b> {interp_text}", self.styles['Normal']))
        
        return story
    
    def _create_flagged_clauses_section(self, analysis_result: Dict) -> List:
        """Create flagged clauses section with redlining"""
        story = []
        
        story.append(Paragraph("FLAGGED CLAUSES", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        flagged_clauses = analysis_result.get('flagged_clauses', [])
        
        if not flagged_clauses:
            story.append(Paragraph("No violations detected.", self.styles['Normal']))
            return story
        
        for i, clause in enumerate(flagged_clauses, 1):
            # Clause header
            category = clause.get('category', 'Unknown')
            severity = clause.get('severity', 'MEDIUM')
            
            header_text = f"{i}. {category} ({severity})"
            story.append(Paragraph(header_text, self.styles['Heading3']))
            story.append(Spacer(1, 0.1*inch))
            
            # Clause text (redlined)
            clause_text = clause.get('clause_text', '')
            redlined = f'<font color="red"><i>"{clause_text}"</i></font>'
            story.append(Paragraph(redlined, self.styles['ClauseText']))
            story.append(Spacer(1, 0.1*inch))
            
            # Plain English explanation
            explanation = clause.get('plain_english', '')
            story.append(Paragraph(f"<b>Explanation:</b> {explanation}", self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
            
            # Red flag
            red_flag = clause.get('red_flag', '')
            story.append(Paragraph(f"<b>Legal Concern:</b> {red_flag}", self.styles['WarningText']))
            
            story.append(Spacer(1, 0.3*inch))
        
        return story
    
    def _create_liability_section(self, analysis_result: Dict) -> List:
        """Create liability calculations section"""
        story = []
        
        story.append(Paragraph("POTENTIAL LIABILITY ANALYSIS", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        liability_report = analysis_result.get('liability_report', {})
        
        # Overview
        overview_text = """
        The following liability estimates are based on statutory penalties, class action modeling, 
        attorney fees, and litigation costs. These are ESTIMATES ONLY and actual liability 
        will depend on many factors including jurisdiction, willfulness, and settlement negotiations.
        """
        story.append(Paragraph(overview_text, self.styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Liability summary table
        liability_data = [
            ["Component", "Amount"],
            ["Statutory Penalties", f"${liability_report.get('statutory_penalties_expected', 0):,}"],
        ]
        
        if liability_report.get('class_action_applicable'):
            liability_data.append([
                "Class Action Damages",
                f"${liability_report.get('class_action_total', 0):,}"
            ])
        
        liability_data.extend([
            ["Attorney Fees", f"${liability_report.get('attorney_fees', 0):,}"],
            ["Litigation Costs", f"${liability_report.get('litigation_costs', 0):,}"],
            ["TOTAL EXPECTED", f"${liability_report.get('total_liability_expected', 0):,}"],
        ])
        
        liability_table = Table(liability_data, colWidths=[3*inch, 2*inch])
        liability_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TITLE_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(liability_table)
        
        # Range
        story.append(Spacer(1, 0.2*inch))
        range_text = f"""
        <b>Liability Range:</b> ${liability_report.get('total_liability_min', 0):,} 
        to ${liability_report.get('total_liability_max', 0):,}
        """
        story.append(Paragraph(range_text, self.styles['Normal']))
        
        # Warnings
        warnings = liability_report.get('warnings', [])
        if warnings:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("<b>Risk Warnings:</b>", self.styles['Heading3']))
            for warning in warnings:
                story.append(Paragraph(f"• {warning}", self.styles['WarningText']))
        
        return story
    
    def _create_recommendations(self, analysis_result: Dict) -> List:
        """Create recommendations section"""
        story = []
        
        story.append(Paragraph("RECOMMENDATIONS", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        recommendation = analysis_result.get('recommendation', 'NEGOTIATE')
        
        rec_text = {
            'REJECT': "We recommend REJECTING this contract. The terms are heavily one-sided and likely contain unenforceable provisions.",
            'NEGOTIATE': "We recommend NEGOTIATING this contract. Significant improvements can be made to protect consumer rights.",
            'ACCEPT_WITH_CAUTION': "The contract may be acceptable with caution. Review the flagged clauses carefully.",
            'ACCEPT': "The contract appears generally fair with minimal concerns."
        }
        
        rec_paragraph = rec_text.get(recommendation, "Review recommended.")
        story.append(Paragraph(f"<b>{rec_paragraph}</b>", self.styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Next steps
        story.append(Paragraph("Suggested Next Steps:", self.styles['Heading3']))
        
        next_steps = [
            "Consult with a licensed attorney for legal advice specific to your situation",
            "Request modifications to the most concerning clauses identified in this report",
            "Consider alternative service providers with more consumer-friendly terms",
            "Document all communications regarding contract negotiations"
        ]
        
        for step in next_steps:
            story.append(Paragraph(f"• {step}", self.styles['Normal']))
        
        return story
    
    def _create_disclaimer(self) -> List:
        """Create legal disclaimer"""
        story = []
        
        story.append(Paragraph("LEGAL DISCLAIMER", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        disclaimer_text = """
        This report is generated by LexRisk AI-powered contract analysis and is provided for 
        informational purposes only. This report does NOT constitute legal advice and should 
        not be relied upon as a substitute for consultation with a licensed attorney.
        
        LexRisk is an AI-assisted tool and may not identify all potential issues in a contract. 
        The analysis is based on general legal principles and may not account for all jurisdictional 
        variations or specific factual circumstances.
        
        Liability estimates are approximations based on statutory penalty schedules and historical 
        settlement data. Actual liability will depend on many factors including but not limited to: 
        jurisdiction, willfulness of violations, company revenue, settlement negotiations, and 
        judicial discretion.
        
        For legal advice tailored to your specific situation, please consult with a licensed attorney 
        in your jurisdiction.
        
        This report is confidential and intended solely for the named recipient. Unauthorized 
        distribution or use is prohibited.
        """
        
        story.append(Paragraph(disclaimer_text, self.styles['Normal']))
        
        # Signature block
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            f"Generated by LexRisk on {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}",
            self.styles['Normal']
        ))
        
        return story


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_litigation_pdf(
    analysis_result: Dict,
    contract_name: str = "Untitled Contract",
    client_name: Optional[str] = None
) -> bytes:
    """
    Convenience function to generate PDF.
    
    Args:
        analysis_result: Analysis result dictionary
        contract_name: Contract name
        client_name: Optional client name
        
    Returns:
        PDF bytes
    """
    generator = LitigationShieldPDF()
    return generator.generate_report(analysis_result, contract_name, client_name)


def is_pdf_export_available() -> bool:
    """Check if PDF export is available"""
    return REPORTLAB_AVAILABLE
