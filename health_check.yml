#!/usr/bin/env python3
"""
health_check.py — Automated Health Check for LexRisk
Tests end-to-end functionality with a dummy contract.

Exit codes:
- 0: Success
- 1: API failure
- 2: Circuit breaker triggered
- 3: Timeout
- 4: Invalid response
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test contract (short, fast to analyze)
TEST_CONTRACT = """
TERMS OF SERVICE

By using this service, you agree that we can change these terms at any time 
without notice. We are not liable for any damages, even if caused by our 
negligence. You may not sue us or join a class action lawsuit. All disputes 
must be resolved through binding arbitration in our home jurisdiction.

We own all content you upload forever, and may use it commercially without 
compensation. Your account can be terminated at any time without refund.
"""

# Expected response validation
EXPECTED_RISK_RANGE = (60, 95)  # Should detect several predatory clauses
EXPECTED_MIN_CLAUSES = 3

def test_analyzer_import() -> bool:
    """Test that analyzer module loads correctly"""
    try:
        from analyzer import ClauseAnalyzer
        logger.info("✅ Analyzer module imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to import analyzer: {e}")
        return False


def test_circuit_breaker_import() -> bool:
    """Test that circuit breaker module loads correctly"""
    try:
        from circuit_breaker import get_openai_circuit_breaker
        breaker = get_openai_circuit_breaker()
        state = breaker.get_state()
        logger.info(f"✅ Circuit breaker operational (state: {state})")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to import circuit breaker: {e}")
        return False


def test_groq_api() -> Dict[str, Any]:
    """Test Groq API with dummy contract"""
    try:
        from analyzer import ClauseAnalyzer
        
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            logger.error("❌ GROQ_API_KEY not found in environment")
            return {"success": False, "error": "Missing API key"}
        
        logger.info("Testing Groq API...")
        start_time = time.time()
        
        analyzer = ClauseAnalyzer(api_key=groq_key, provider="groq")
        result = analyzer.analyze(TEST_CONTRACT)
        
        processing_time = time.time() - start_time
        
        # Validate response
        if not validate_analysis_result(result):
            return {"success": False, "error": "Invalid response structure"}
        
        logger.info(
            f"✅ Groq API test passed - "
            f"Score: {result.risk_score}, "
            f"Clauses: {len(result.flagged_clauses)}, "
            f"Time: {processing_time:.2f}s"
        )
        
        return {
            "success": True,
            "risk_score": result.risk_score,
            "flagged_clauses": len(result.flagged_clauses),
            "processing_time": processing_time,
            "risk_level": result.risk_level
        }
        
    except Exception as e:
        logger.error(f"❌ Groq API test failed: {e}")
        return {"success": False, "error": str(e)}


def test_openai_api() -> Dict[str, Any]:
    """Test OpenAI API with dummy contract"""
    try:
        from analyzer import ClauseAnalyzer
        
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            logger.warning("⚠️ OPENAI_API_KEY not found - skipping OpenAI test")
            return {"success": True, "skipped": True}
        
        logger.info("Testing OpenAI API...")
        start_time = time.time()
        
        analyzer = ClauseAnalyzer(api_key=openai_key, provider="openai")
        result = analyzer.analyze(TEST_CONTRACT)
        
        processing_time = time.time() - start_time
        
        # Validate response
        if not validate_analysis_result(result):
            return {"success": False, "error": "Invalid response structure"}
        
        logger.info(
            f"✅ OpenAI API test passed - "
            f"Score: {result.risk_score}, "
            f"Clauses: {len(result.flagged_clauses)}, "
            f"Time: {processing_time:.2f}s"
        )
        
        return {
            "success": True,
            "risk_score": result.risk_score,
            "flagged_clauses": len(result.flagged_clauses),
            "processing_time": processing_time,
            "risk_level": result.risk_level
        }
        
    except Exception as e:
        logger.error(f"❌ OpenAI API test failed: {e}")
        return {"success": False, "error": str(e)}


def validate_analysis_result(result) -> bool:
    """Validate that analysis result meets expectations"""
    try:
        # Check required fields exist
        required_fields = ['risk_score', 'risk_level', 'flagged_clauses', 'summary']
        for field in required_fields:
            if not hasattr(result, field):
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate risk score range
        if not (0 <= result.risk_score <= 100):
            logger.error(f"Risk score out of range: {result.risk_score}")
            return False
        
        # For our test contract, expect meaningful flagged clauses
        if len(result.flagged_clauses) < EXPECTED_MIN_CLAUSES:
            logger.warning(
                f"Expected at least {EXPECTED_MIN_CLAUSES} flagged clauses, "
                f"got {len(result.flagged_clauses)}"
            )
            # Warning only, not a hard failure
        
        # Validate risk score is reasonable for predatory test contract
        min_score, max_score = EXPECTED_RISK_RANGE
        if not (min_score <= result.risk_score <= max_score):
            logger.warning(
                f"Risk score {result.risk_score} outside expected range "
                f"{EXPECTED_RISK_RANGE} for test contract"
            )
            # Warning only, not a hard failure
        
        return True
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


def test_telemetry_logging() -> bool:
    """Test that telemetry logging works"""
    try:
        from telemetry import log_analysis_telemetry, get_telemetry_summary
        
        # Log a test entry
        analysis_id = log_analysis_telemetry(
            user_id="health_check",
            contract_length=len(TEST_CONTRACT),
            risk_score=75,
            risk_level="HIGH",
            engine_used="groq",
            was_cached=False,
            processing_time_ms=1000,
            contract_type="test"
        )
        
        if analysis_id is None:
            logger.error("❌ Failed to log telemetry")
            return False
        
        # Verify we can retrieve summary
        summary = get_telemetry_summary(days=1)
        
        if not summary:
            logger.warning("⚠️ Telemetry summary returned empty (may be expected)")
        
        logger.info("✅ Telemetry logging operational")
        return True
        
    except Exception as e:
        logger.error(f"❌ Telemetry test failed: {e}")
        return False


def run_all_checks() -> int:
    """
    Run all health checks and return exit code.
    
    Returns:
        0: All checks passed
        1: Critical failure
    """
    logger.info("=" * 80)
    logger.info("LexRisk Health Check")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    checks_passed = 0
    checks_total = 0
    critical_failure = False
    
    # Test 1: Module imports
    checks_total += 1
    if test_analyzer_import():
        checks_passed += 1
    else:
        critical_failure = True
    
    checks_total += 1
    if test_circuit_breaker_import():
        checks_passed += 1
    
    # Test 2: Groq API (critical)
    checks_total += 1
    groq_result = test_groq_api()
    if groq_result.get("success"):
        checks_passed += 1
    else:
        critical_failure = True
    
    # Test 3: OpenAI API (non-critical)
    checks_total += 1
    openai_result = test_openai_api()
    if openai_result.get("success") or openai_result.get("skipped"):
        checks_passed += 1
    
    # Test 4: Telemetry (non-critical)
    checks_total += 1
    if test_telemetry_logging():
        checks_passed += 1
    
    # Summary
    logger.info("=" * 80)
    logger.info(f"Health Check Summary: {checks_passed}/{checks_total} checks passed")
    
    if critical_failure:
        logger.error("❌ CRITICAL FAILURE - System is not operational")
        return 1
    elif checks_passed == checks_total:
        logger.info("✅ ALL CHECKS PASSED - System is fully operational")
        return 0
    else:
        logger.warning("⚠️ SOME CHECKS FAILED - System is partially operational")
        return 0  # Non-critical failures don't trigger alerts
    
    logger.info("=" * 80)


if __name__ == "__main__":
    exit_code = run_all_checks()
    sys.exit(exit_code)
