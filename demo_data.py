import json
import os
from analyzer import ClauseAnalyzer
"""
analyzer.py
Core Groq integration — scans contract text for predatory clauses.
"""

import logging
import os
import json
import re
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
  "score": 0,
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
    disclaimer: str

# ── Analyzer ──────────────────────────────────────────────────────────────────

class ClauseAnalyzer:
    def __init__(self, api_key: str | None = None):
        # Try multiple sources for API key
        if api_key:
            self.api_key = api_key
        else:
            try:
                import streamlit as st
                self.api_key = st.secrets.get("GROQ_API_KEY")
            except:
                self.api_key = os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set. Add it to Streamlit secrets or .env file.")
        
        self.client = Groq(api_key=self.api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "2048"))
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

        logger.info(f"ClauseAnalyzer initialized with model: {self.model}")

    def analyze(self, contract_text: str) -> AnalysisResult:
        """Analyze contract text for predatory clauses."""
        if not contract_text or not contract_text.strip():
            raise ValueError("Contract text cannot be empty.")

        logger.info(f"Analyzing contract ({len(contract_text)} chars)...")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                        contract_text=contract_text[:8000]
                    )}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            raw = response.choices[0].message.content
            logger.info("Groq inference successful.")
            return self._parse_response(raw)

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def _parse_response(self, raw: str) -> AnalysisResult:
        """Parse Groq JSON response into AnalysisResult."""
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
            disclaimer=legal_notice
        )
analyzer = ClauseAnalyzer()

# THIS LINE FIXES THE ERROR
demos_data = {} 

files = {
    'x_tos': 'demos/x_tos.txt',
    'tiktok': 'demos/tiktik_tos.txt', 
    'gym': 'demos/gym_agreement.txt',
    'nda': 'demos/nda_agreement.txt'
}
for key, filename in files.items():
    print(f"Analyzing {filename}...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()
    
    result = analyzer.analyze(text)
    
    demos_data[key] = {
        'title': filename.replace('_', ' ').replace('.txt', '').title(),
        'text': text,
        'analysis': {
            'risk_score': result.risk_score,
            'risk_level': result.risk_level,
            'flagged_clauses': [
                {
                    'clause_text': c.clause_text,
                    'category': c.category,
                    'severity': c.severity,
                    'plain_english': c.plain_english,
                    'red_flag': c.red_flag
                }
                for c in result.flagged_clauses
            ],
            'summary': result.summary,
            'recommendation': result.recommendation
        }
    }
    
    print(f"✓ {key}: Risk {result.risk_score}/100")

# Save to Python file
with open('demo_data.py', 'w') as f:
    f.write("DEMOS = ")
    f.write(json.dumps(demos_data, indent=2))

print("\n✓ Generated demo_data.py")
