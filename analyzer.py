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


# ── Analyzer ──────────────────────────────────────────────────────────────────

class ClauseAnalyzer:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set. Add it to your .env file.")

        self.client = Groq(api_key=self.api_key)
        self.model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        self.max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "2048"))
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

        logger.info(f"ClauseAnalyzer initialized with model: {self.model}")

    def analyze(self, contract_text: str) -> AnalysisResult:
        """
        Analyze contract text for predatory clauses.
        Returns structured AnalysisResult.
        """
        if not contract_text or not contract_text.strip():
            raise ValueError("Contract text cannot be empty.")

        logger.info(f"Analyzing contract ({len(contract_text)} chars)...")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                        contract_text=contract_text[:8000]  # stay within token limits
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
        import json
        import re

        # Strip markdown code fences if present
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nRaw: {raw}")
            raise ValueError(f"Model returned invalid JSON: {e}")

        flagged = [
            FlaggedClause(
                clause_text=c.get("clause_text", ""),
                category=c.get("category", "Unknown"),
                severity=c.get("severity", "MEDIUM"),
                plain_english=c.get("plain_english", ""),
                red_flag=c.get("red_flag", ""),
            )
            for c in data.get("flagged_clauses", [])
        ]

        return AnalysisResult(
            risk_score=int(data.get("risk_score", 0)),
            risk_level=data.get("risk_level", "LOW"),
            flagged_clauses=flagged,
            summary=data.get("summary", ""),
            recommendation=data.get("recommendation", "SIGN"),
            raw_response=raw,
        )
