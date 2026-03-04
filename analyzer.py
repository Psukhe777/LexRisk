"""
analyzer.py
Core AI integration — Scans contract text for predatory clauses using 
the expanded "Ruthless Lawyer" matrix and dual LLM routing (Groq / Gemini).

FEATURES:
1. Intelligent dual-engine router (Groq for short, Gemini for long/complex)
2. Industry-standard calibration layer
3. Contract type detection
4. Improved scoring logic to prevent false positives
"""

import logging
import os
import json
import re
from dataclasses import dataclass
from typing import Optional

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

# ── NEW: Calibration Prompt (appended to system prompt for Gemini) ──
CALIBRATION_ADDENDUM = """CRITICAL CALIBRATION RULES:
- Industry Standard vs. Predatory: Distinguish between standard practice and actual abuse.
- Social Media/Platform ToS: Standard content licenses (for display/moderation) are NOT IP theft. Score 40-60 unless they claim commercial rights.
- SaaS/B2B: Standard limitation of liability (1-12 months fees) is NOT predatory. Flag only if capped under $100.
- Consumer Apps: Arbitration + Class Action waiver is HIGH (75-85), not CRITICAL, unless combined with gag clauses.
- Score 90+: Reserved for literal scams, total loss of rights, or contracts that would bankrupt the user.
- Score 85-89: Extreme one-sidedness (e.g., they can terminate without refund AND keep your IP AND sue you).
- Score 70-84: Aggressive but common in Big Tech (negotiate if possible).
- Score 40-69: Standard with some concerning clauses (read carefully).
- Score 0-39: Consumer-friendly or fair B2B terms.
When in doubt, assume the contract is from a legitimate company, not a scam operation."""

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
    engine_used: str = "groq"  
    contract_type: str = "Unknown"  

# ── 3. Contract Type Detector ─────────────────────────────────────────────────

class ContractTypeDetector:
    """Detect contract type to calibrate scoring appropriately"""
    
    @staticmethod
    def detect(text: str) -> dict:
        """
        Returns: {
            "type": "social_media" | "saas" | "b2b" | "consumer" | "employment" | "unknown",
            "confidence": 0.0-1.0,
            "indicators": [list of matched keywords]
        }
        """
        text_lower = text.lower()
        
        # Social Media Platform Detection
        social_keywords = ["tweet", "retweet", "post content", "user-generated content", 
                           "social network", "followers", "timeline", "feed"]
        social_score = sum(1 for k in social_keywords if k in text_lower)
        
        # SaaS Detection
        saas_keywords = ["software as a service", "subscription", "api access", 
                         "service level", "uptime", "cloud service"]
        saas_score = sum(1 for k in saas_keywords if k in text_lower)
        
        # B2B Detection
        b2b_keywords = ["enterprise", "vendor", "procurement", "statement of work", 
                        "master service agreement", "purchase order"]
        b2b_score = sum(1 for k in b2b_keywords if k in text_lower)
        
        # Consumer App Detection
        consumer_keywords = ["end user", "consumer", "personal use", "free account", 
                            "premium subscription", "in-app purchase"]
        consumer_score = sum(1 for k in consumer_keywords if k in text_lower)
        
        # Employment Detection
        employment_keywords = ["employee", "employer", "employment agreement", 
                              "confidential information", "non-compete", "stock options"]
        employment_score = sum(1 for k in employment_keywords if k in text_lower)
        
        scores = {
            "social_media": social_score,
            "saas": saas_score,
            "b2b": b2b_score,
            "consumer": consumer_score,
            "employment": employment_score
        }
        
        detected_type = max(scores, key=scores.get)
        max_score = scores[detected_type]
        confidence = min(max_score / 5.0, 1.0)  # 5+ matches = high confidence
        
        if confidence < 0.2:
            detected_type = "unknown"
            
        return {
            "type": detected_type,
            "confidence": confidence,
            "indicators": [k for k, v in scores.items() if v > 0]
        }

# ── 4. Dual-Engine Router ─────────────────────────────────────────────────────

class EngineRouter:
    """Intelligently routes to Groq (fast, aggressive) or Gemini (nuanced, calibrated)"""
    
    @staticmethod
    def choose_engine(contract_text: str, contract_type: str) -> str:
        text_length = len(contract_text)
        
        # Route to Gemini for:
        if text_length > 4000:
            logger.info(f"Routing to GEMINI: Long contract ({text_length} chars)")
            return "gemini"
        if contract_type == "social_media":
            logger.info("Routing to GEMINI: Social media platform (needs calibration)")
            return "gemini"
        if contract_type == "unknown":
            logger.info("Routing to GEMINI: Unknown contract type (safer)")
            return "gemini"
        if contract_type == "consumer" and text_length > 2000:
            logger.info("Routing to GEMINI: Complex consumer app")
            return "gemini"
            
        # Route to Groq for short, B2B, or Employment contracts
        logger.info(f"Routing to GROQ: {contract_type} contract ({text_length} chars)")
        return "groq"

# ── 5. Analyzer Engine (ENHANCED) ─────────────────────────────────────────────

class ClauseAnalyzer:
    def __init__(self, api_key: str = None, groq_key: str = None, gemini_key: str = None, provider: str = "auto"):
        self.provider = provider.lower()
        
        # SAFELY fetch keys from arguments, Streamlit secrets, or Environment variables
        try:
            import streamlit as st
            st_groq = st.secrets.get("GROQ_API_KEY")
            st_gemini = st.secrets.get("GEMINI_API_KEY")
        except:
            st_groq = None
            st_gemini = None
            
        self.groq_key = groq_key or (api_key if self.provider in ["groq", "auto"] else None) or st_groq or os.getenv("GROQ_API_KEY")
        self.gemini_key = gemini_key or (api_key if self.provider in ["gemini", "auto"] else None) or st_gemini or os.getenv("GEMINI_API_KEY")
        
        # Initialize Groq if available
        if self.groq_key:
            try:
                self.groq_client = Groq(api_key=self.groq_key)
                self.groq_model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
                logger.info("✅ Groq engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Groq initialization failed: {e}")
                self.groq_client = None
        else:
            self.groq_client = None
            logger.warning("⚠️ No Groq API key provided")
            
        # Initialize Gemini if available
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
                logger.info("✅ Gemini engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Gemini initialization failed: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None
            logger.warning("⚠️ No Gemini API key provided")
            
        # Validate at least one engine is available
        if not self.groq_client and not self.gemini_model:
            raise ValueError("At least one API key (Groq or Gemini) must be provided in Streamlit secrets or .env")
            
        logger.info(f"ClauseAnalyzer initialized with provider mode: {self.provider.upper()}")

    def analyze(self, contract_text: str, force_engine: Optional[str] = None) -> AnalysisResult:
        if not contract_text or not contract_text.strip():
            raise ValueError("Contract text cannot be empty.")

        logger.info(f"Analyzing contract ({len(contract_text)} chars)...")
        
        contract_info = ContractTypeDetector.detect(contract_text)
        logger.info(f"Contract type detected: {contract_info['type']} (confidence: {contract_info['confidence']:.2f})")
        
        if force_engine:
            chosen_engine = force_engine.lower()
            logger.info(f"Engine override: {chosen_engine.upper()}")
        elif self.provider == "auto":
            chosen_engine = EngineRouter.choose_engine(contract_text, contract_info['type'])
        else:
            chosen_engine = self.provider
            
        if chosen_engine == "groq" and not self.groq_client:
            if self.gemini_model:
                logger.warning("Groq requested but unavailable, falling back to Gemini")
                chosen_engine = "gemini"
            else:
                raise ValueError("Groq engine not available and no fallback configured")
                
        if chosen_engine == "gemini" and not self.gemini_model:
            if self.groq_client:
                logger.warning("Gemini requested but unavailable, falling back to Groq")
                chosen_engine = "groq"
            else:
                raise ValueError("Gemini engine not available and no fallback configured")
                
        try:
            if chosen_engine == "groq":
                raw_json = self._call_groq(contract_text)
            else:
                raw_json = self._call_gemini(contract_text)
                
            result = self._parse_and_enforce_matrix(raw_json, contract_info['type'])
            result.engine_used = chosen_engine
            result.contract_type = contract_info['type']
            
            logger.info(f"Analysis complete: Score={result.risk_score}, Level={result.risk_level}, Engine={chosen_engine}")
            return result

        except Exception as e:
            logger.error(f"API error ({chosen_engine}): {e}")
            raise

    # ── LLM Calling Logic ──

    def _call_groq(self, contract_text: str) -> str:
        response = self.groq_client.chat.completions.create(
            model=self.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                    contract_text=contract_text[:30000]
                )}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    def _call_gemini(self, contract_text: str) -> str:
        enhanced_prompt = f"{SYSTEM_PROMPT}\n\n{CALIBRATION_ADDENDUM}"
        full_prompt = f"{enhanced_prompt}\n\n{USER_PROMPT_TEMPLATE.format(contract_text=contract_text[:30000])}"
        
        response = self.gemini_model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return response.text

    # ── The Expanded Deterministic Scoring Matrix (CALIBRATED) ──

    def _parse_and_enforce_matrix(self, raw: str, contract_type: str) -> AnalysisResult:
        """Parse LLM response and apply deterministic scoring with contract-type calibration"""
        # Strip markdown fences if present
        clean = re.sub(r"^```json\n|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(clean)

        base_score = int(data.get("score", 0))
        flagged_clauses_data = data.get("flags", [])
        
        # 🛡️ THE DETERMINISTIC PENALTY MATRIX 🛡️
