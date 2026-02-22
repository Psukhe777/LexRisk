"""
""
clause/src/analyzer.py
Core Groq integration — scans contract text for predatory clauses.
"""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Role: CLAUSE, expert AI legal analyst.
Task: Extract predatory/dangerous clauses from contracts into strict JSON.

Rules:
- Output ONLY valid JSON. No markdown, no preamble.
- Flag only genuinely concerning clauses; ignore standard boilerplate.
- If none found: empty `flags` array, low `score`.

JSON Format:
{
  "score": int, // 0-100
  "lvl": "LOW|MEDIUM|HIGH|CRITICAL",
  "flags": [
    {
      "txt": "Exact excerpt",
      "cat": "Category (e.g., Arbitration, Auto-Renewal)",
      "sev": "LOW|MEDIUM|HIGH|CRITICAL",
      "desc": "1-2 sentence plain-English explanation",
      "red": "Specific red flag"
    }
  ],
  "sum": "2-3 sentence overall assessment",
  "rec": "SIGN|NEGOTIATE|AVOID"
}"""

USER_PROMPT_TEMPLATE = """Contract:
---
{contract_text}
---"""

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class FlaggedClause:
    clause_text: str
    category: str
    severity: str
    plain_english: str
    red_flag: str

@dataclass
class AnalysisResult:
    risk_score: int
    risk_level: str
    flagged_clauses: list[FlaggedClause]
    summary: str
    recommendation: str
    raw_response: str
    disclaimer: str  # <--- NEW FIELD

# ── Analyzer ──────────────────────────────────────────────────────────────────

class ClauseAnalyzer:
    # ... (keep your __init__ and analyze methods) ...

    def _parse_response(self, raw: str) -> AnalysisResult:
        import json
        import re
        
        # Strip markdown fences
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(clean)

        # Standard legal disclaimer text
        legal_notice = (
            "Lexrisk is an AI-powered assistant, not a legal professional. "
            "This analysis is for informational purposes only and does not constitute "
            "legal advice or an attorney-client relationship."
        )

        flagged = [
            FlaggedClause(
                clause_text=c.get("txt", ""),
                category=c.get("cat", "General"),
                severity=c.get("sev", "MEDIUM"),
                plain_english=c.get("desc", ""),
                red_flag=c.get("red", ""),
            )
            for c in data.get("flags", [])
        ]

        return AnalysisResult(
            risk_score=int(data.get("score", 0)),
            risk_level=data.get("lvl", "LOW"),
            flagged_clauses=flagged,
            summary=data.get("sum", ""),
            recommendation=data.get("rec", "SIGN"),
            raw_response=raw,
            disclaimer=legal_notice # <--- INJECTED HERE
        )
