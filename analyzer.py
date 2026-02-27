"""
analyzer.py
Core AI integration — Scans contract text for predatory clauses using 
the expanded "Ruthless Lawyer" matrix and dual LLM routing (Groq / Gemini).
"""

import logging
import os
import json
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from groq import Groq
import google.generativeai as genai

load_dotenv()
logger = logging.getLogger(__name__)

# ── 1. The Expanded "Ruthless Lawyer" System Prompt ───────────────────────────

SYSTEM_PROMPT = """You are LEXRISK, an elite, ruthless corporate lawyer auditing contracts.
Your sole job is to protect the user from predatory, one-sided, and dangerous legal clauses.

You are hunting for the following 15 threat vectors:
1. Binding Arbitration & Class Action Waivers (Stripping the right to sue).
2. Unilateral Modification (They can change the rules/pricing without notice).
3. Perpetual Licensing / IP Theft (They own the user's content forever).
4. Auto-Renewal / Predatory Billing (Trapping the user in payments).
5. Broad Indemnification (Making the user pay for the company's legal mistakes).
6. Severe Limitation of Liability (Capping their damages to absurdly low amounts like $50).
7. Non-Disparagement / Gag Clauses (Forbidding the user from leaving bad reviews publicly).
8. Inconvenient Venue / Governing Law (Forcing lawsuits to happen in a foreign country or distant state).
9. Termination for Convenience (Deleting the user's account and data at any time, without cause or refund).
10. Right to Audit (B2B: Allowing the vendor to physically or digitally audit the user's systems without reasonable notice).
11. Non-Compete / Exclusivity (B2B: Preventing the user from using competitor products or building similar solutions).
12. Data Monetization / Shadow Sharing (Selling user data to unvetted third parties without explicit opt-in).
13. Hidden Penalties / Liquidated Damages (Massive financial penalties for minor breaches of contract).
14. Post-Termination Survival (Dangerous clauses like IP licenses that survive even after the user deletes their account).
15. Unilateral Injunctive Relief (Allowing the company to freeze the user's assets or operations without posting a bond).

Rules:
- Output ONLY valid JSON. No markdown, no preamble.
- Flag ONLY genuinely concerning clauses. Ignore standard boilerplate.
- Be brutal but accurate in your plain-English descriptions.

JSON Format:
{
  "score": 0,
  "lvl": "LOW|MEDIUM|HIGH|CRITICAL",
  "flags": [
    {
      "txt": "Exact excerpt from the text",
      "cat": "Category (e.g., Arbitration, IP Rights, Gag Clause)",
      "sev": "LOW|MEDIUM|HIGH|CRITICAL",
      "desc": "1-2 sentence plain-English explanation of why this hurts the user",
      "red": "Specific red flag (e.g., 'Allows them to sell your medical data')"
    }
  ],
  "sum": "2-3 sentence overall ruthless assessment of the contract",
  "rec": "SIGN|NEGOTIATE|AVOID"
}"""

USER_PROMPT_TEMPLATE = """Contract Text:
---
{contract_text}
---
Analyze the contract and return the JSON."""

# ── 2. Data Classes ───────────────────────────────────────────────────────────

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

# ── 3. Analyzer Engine ────────────────────────────────────────────────────────

class ClauseAnalyzer:
    def __init__(self, api_key: str, provider: str = "groq"):
        self.provider = provider.lower()
        self.api_key = api_key

        if not self.api_key:
            raise ValueError(f"API Key for {self.provider} is missing.")

        if self.provider == "groq":
            self.client = Groq(api_key=self.api_key)
            self.model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
            self.temperature = 0.1 
        elif self.provider == "gemini":
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        logger.info(f"ClauseAnalyzer initialized with provider: {self.provider.upper()}")

    def analyze(self, contract_text: str) -> AnalysisResult:
        if not contract_text or not contract_text.strip():
            raise ValueError("Contract text cannot be empty.")

        logger.info(f"Analyzing contract ({len(contract_text)} chars) via {self.provider}...")

        try:
            if self.provider == "groq":
                raw_json = self._call_groq(contract_text)
            elif self.provider == "gemini":
                raw_json = self._call_gemini(contract_text)
            
            return self._parse_and_enforce_matrix(raw_json)

        except Exception as e:
            logger.error(f"API error ({self.provider}): {e}")
            raise

    # ── LLM Calling Logic ──

    def _call_groq(self, contract_text: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                    contract_text=contract_text[:30000]
                )}
            ],
            temperature=self.temperature,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    def _call_gemini(self, contract_text: str) -> str:
        prompt = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT_TEMPLATE.format(contract_text=contract_text)}"
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return response.text

    # ── The Expanded Deterministic Scoring Matrix ──

    def _parse_and_enforce_matrix(self, raw: str) -> AnalysisResult:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        data = json.loads(clean)

        base_score = int(data.get("score", 0))
        flagged_clauses_data = data.get("flags", [])
        
        # 🛡️ THE DETERMINISTIC PENALTY MATRIX 🛡️
        for clause in flagged_clauses_data:
            text_lower = str(clause.get("txt", "")).lower()
            cat_lower = str(clause.get("cat", "")).lower()
            
            # Tier 1: Absolute Dealbreakers (90-95)
            if "class action" in text_lower or "class action" in cat_lower:
                base_score = max(base_score, 95)
                clause["sev"] = "CRITICAL"
            elif "arbitration" in text_lower or "arbitration" in cat_lower:
                base_score = max(base_score, 90)
                clause["sev"] = "CRITICAL"
            elif "non-compete" in text_lower or "exclusivity" in cat_lower or "compete" in cat_lower:
                base_score = max(base_score, 90)
                clause["sev"] = "CRITICAL"
            
            # Tier 2: Severe Risk / Predatory (75-85)
            elif "indemnify" in text_lower or "indemnification" in cat_lower:
                base_score = max(base_score, 85)
                clause["sev"] = "HIGH"
            elif "disparagement" in text_lower or "gag" in cat_lower:
                base_score = max(base_score, 85)
                clause["sev"] = "HIGH"
            elif "unilateral" in text_lower or "modify" in cat_lower:
                base_score = max(base_score, 75)
                clause["sev"] = "HIGH"
            elif "monetize" in text_lower or "sell data" in text_lower or "third party" in cat_lower:
                base_score = max(base_score, 80)
                clause["sev"] = "HIGH"
            elif "liquidated" in text_lower or "penalty" in cat_lower:
                base_score = max(base_score, 75)
                clause["sev"] = "HIGH"
            elif "liability" in cat_lower and ("cap" in text_lower or "limit" in text_lower):
                base_score = max(base_score, 75)
                clause["sev"] = "HIGH"

            # Tier 3: Medium Risk / Aggressive (60-70)
            elif "audit" in cat_lower or "inspection" in text_lower:
                base_score = max(base_score, 70)
                clause["sev"] = "MEDIUM"
            elif "termination for convenience" in text_lower or "without cause" in text_lower:
                base_score = max(base_score, 65)
                clause["sev"] = "MEDIUM"
            elif "venue" in cat_lower or "jurisdiction" in cat_lower:
                base_score = max(base_score, 60)
                clause["sev"] = "MEDIUM"
            elif "auto-renew" in text_lower or "renewal" in cat_lower:
                base_score = max(base_score, 60)
                clause["sev"] = "MEDIUM"

        # Cap at 100
        final_score = min(base_score, 100)

        if final_score >= 85:
            final_lvl = "CRITICAL"
            final_rec = "AVOID"
        elif final_score >= 70:
            final_lvl = "HIGH"
            final_rec = "NEGOTIATE"
        elif final_score >= 40:
            final_lvl = "MEDIUM"
            final_rec = "NEGOTIATE"
        else:
            final_lvl = "LOW"
            final_rec = "SIGN"

        legal_notice = (
            "Lexrisk is an AI-powered assistant, not a legal professional. "
            "This analysis is for informational purposes only and does not constitute "
            "legal advice or an attorney-client relationship."
        )

        flagged_objects = [
            FlaggedClause(
                clause_text=c.get("txt", ""),
                category=c.get("cat", "General"),
                severity=c.get("sev", "MEDIUM"),
                plain_english=c.get("desc", ""),
                red_flag=c.get("red", "")
            ) for c in flagged_clauses_data
        ]

        return AnalysisResult(
            risk_score=final_score,
            risk_level=final_lvl,
            flagged_clauses=flagged_objects,
            summary=data.get("sum", "Analysis complete."),
            recommendation=final_rec,
            raw_response=raw,
            disclaimer=legal_notice
        )
