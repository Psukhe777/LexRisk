"""
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

SYSTEM_PROMPT = """You are CLAUSE, an expert AI legal analyst specializing in identifying predatory, 
unfair, or dangerous clauses in contracts and Terms of Service documents.

Your job is to analyze the provided contract text and return a structured JSON response identifying:
1. Predatory or harmful clauses
2. A risk score (0–100)
3. Plain-English explanations a non-lawyer can understand

Respond ONLY with valid JSON in this exact format:
{
  "risk_score": <integer 0-100>,
  "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "flagged_clauses": [
    {
      "clause_text": "<exact excerpt from the contract>",
      "category": "<e.g. Auto-Renewal, Arbitration, Data Rights, Liability Waiver, Cancellation>",
      "severity": "<LOW|MEDIUM|HIGH|CRITICAL>",
      "plain_english": "<1-2 sentence explanation of why this is problematic>",
      "red_flag": "<specific thing to watch out for>"
    }
  ],
  "summary": "<2-3 sentence overall assessment>",
  "recommendation": "<SIGN|NEGOTIATE|AVOID>"
}

If no predatory clauses are found, return an empty flagged_clauses array and a low risk score.
Be precise. Only flag genuinely concerning clauses, not standard boilerplate."""

USER_PROMPT_TEMPLATE = """Analyze this contract/TOS text for predatory or unfair clauses:

---
{contract_text}
---

Return your analysis as JSON only."""


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
