"""
telemetry.py — Advanced Data Science Telemetry System
Silently logs all analysis metadata to SQLite for future model training.

Features:
- Thread-safe SQLite operations
- Automatic schema migrations
- Character-level granularity
- Performance profiling
- Error tracking
- Contract type classification
"""

import sqlite3
import threading
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = Path(__file__).parent / "lexrisk_telemetry.db"
_db_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA = """
-- Main analysis telemetry table
CREATE TABLE IF NOT EXISTS analysis_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- User context
    user_id TEXT NOT NULL,
    user_tier TEXT DEFAULT 'free',
    session_id TEXT,
    
    -- Contract metadata
    contract_length INTEGER NOT NULL,
    contract_char_count INTEGER NOT NULL,
    contract_word_count INTEGER,
    contract_paragraph_count INTEGER,
    contract_type TEXT,
    contract_hash TEXT,
    
    -- Analysis results
    risk_score INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    flagged_clause_count INTEGER DEFAULT 0,
    critical_clauses INTEGER DEFAULT 0,
    high_clauses INTEGER DEFAULT 0,
    medium_clauses INTEGER DEFAULT 0,
    low_clauses INTEGER DEFAULT 0,
    
    -- Performance metrics
    engine_used TEXT NOT NULL,
    processing_time_ms INTEGER,
    was_cached BOOLEAN DEFAULT 0,
    was_failover BOOLEAN DEFAULT 0,
    circuit_breaker_state TEXT,
    
    -- Feature flags
    had_pdf_upload BOOLEAN DEFAULT 0,
    pdf_page_count INTEGER,
    text_truncated BOOLEAN DEFAULT 0,
    
    -- ML training labels (future use)
    user_feedback_score INTEGER,
    false_positive BOOLEAN,
    false_negative BOOLEAN,
    
    -- Indexes
    INDEX idx_timestamp (timestamp),
    INDEX idx_user_id (user_id),
    INDEX idx_contract_type (contract_type),
    INDEX idx_risk_level (risk_level),
    INDEX idx_engine_used (engine_used)
);

-- Clause-level telemetry
CREATE TABLE IF NOT EXISTS clause_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER REFERENCES analysis_telemetry(id),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Clause details
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    clause_length INTEGER,
    clause_word_count INTEGER,
    
    -- Position in contract
    clause_position_start INTEGER,
    clause_position_end INTEGER,
    
    -- For training classification models
    clause_text_hash TEXT,
    
    INDEX idx_category (category),
    INDEX idx_severity (severity),
    INDEX idx_analysis_id (analysis_id)
);

-- Error telemetry
CREATE TABLE IF NOT EXISTS error_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    user_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT,
    error_traceback TEXT,
    
    -- Context
    contract_length INTEGER,
    engine_attempted TEXT,
    circuit_breaker_state TEXT,
    
    INDEX idx_error_type (error_type),
    INDEX idx_timestamp (timestamp)
);

-- Performance baseline metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    engine TEXT,
    contract_length_bucket TEXT,
    
    INDEX idx_metric_name (metric_name),
    INDEX idx_timestamp (timestamp)
);

-- User behavior analytics
CREATE TABLE IF NOT EXISTS user_behavior (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_metadata TEXT,
    
    INDEX idx_user_id (user_id),
    INDEX idx_action_type (action_type)
);
"""


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

@contextmanager
def get_db():
    """Thread-safe database connection context manager"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()


def init_telemetry_db():
    """Initialize telemetry database with schema"""
    try:
        with get_db() as conn:
            conn.executescript(SCHEMA)
        logger.info(f"✅ Telemetry database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize telemetry database: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TELEMETRY LOGGING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def log_analysis_telemetry(
    user_id: str,
    contract_length: int,
    risk_score: int,
    risk_level: str,
    engine_used: str,
    was_cached: bool,
    processing_time_ms: int,
    contract_type: str = "unknown",
    user_tier: str = "free",
    flagged_clauses: list = None,
    contract_hash: str = None,
    breaker_state: str = "n/a",
    was_failover: bool = False,
    had_pdf: bool = False,
    pdf_pages: int = 0,
    text_truncated: bool = False
) -> Optional[int]:
    """
    Log comprehensive analysis telemetry.
    
    Returns:
        analysis_id for linking clause-level data
    """
    try:
        # Calculate derived metrics
        word_count = len(contract_length.split()) if isinstance(contract_length, str) else 0
        paragraph_count = contract_length.count('\n\n') if isinstance(contract_length, str) else 0
        
        flagged_clauses = flagged_clauses or []
        clause_count = len(flagged_clauses)
        
        # Count by severity
        critical = sum(1 for c in flagged_clauses if c.get('severity') == 'CRITICAL')
        high = sum(1 for c in flagged_clauses if c.get('severity') == 'HIGH')
        medium = sum(1 for c in flagged_clauses if c.get('severity') == 'MEDIUM')
        low = sum(1 for c in flagged_clauses if c.get('severity') == 'LOW')
        
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO analysis_telemetry (
                    user_id, user_tier, contract_length, contract_char_count,
                    contract_word_count, contract_paragraph_count, contract_type,
                    contract_hash, risk_score, risk_level, flagged_clause_count,
                    critical_clauses, high_clauses, medium_clauses, low_clauses,
                    engine_used, processing_time_ms, was_cached, was_failover,
                    circuit_breaker_state, had_pdf_upload, pdf_page_count, text_truncated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, user_tier, contract_length, contract_length,
                word_count, paragraph_count, contract_type, contract_hash,
                risk_score, risk_level, clause_count, critical, high, medium, low,
                engine_used, processing_time_ms, was_cached, was_failover,
                breaker_state, had_pdf, pdf_pages, text_truncated
            ))
            
            analysis_id = cursor.lastrowid
            
            logger.info(
                f"📊 Telemetry logged: user={user_id}, score={risk_score}, "
                f"engine={engine_used}, cached={was_cached}"
            )
            
            return analysis_id
            
    except Exception as e:
        logger.error(f"Failed to log analysis telemetry: {e}")
        return None


def log_clause_telemetry(
    analysis_id: int,
    category: str,
    severity: str,
    clause_text: str,
    clause_position: tuple = None
):
    """Log individual clause telemetry"""
    try:
        clause_length = len(clause_text)
        clause_word_count = len(clause_text.split())
        clause_hash = hash(clause_text)
        
        start_pos, end_pos = clause_position if clause_position else (None, None)
        
        with get_db() as conn:
            conn.execute("""
                INSERT INTO clause_telemetry (
                    analysis_id, category, severity, clause_length,
                    clause_word_count, clause_text_hash,
                    clause_position_start, clause_position_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id, category, severity, clause_length,
                clause_word_count, str(clause_hash), start_pos, end_pos
            ))
            
    except Exception as e:
        logger.error(f"Failed to log clause telemetry: {e}")


def log_error_telemetry(
    error_type: str,
    error_message: str,
    user_id: str = None,
    contract_length: int = None,
    engine_attempted: str = None,
    breaker_state: str = None,
    traceback: str = None
):
    """Log error events for debugging and monitoring"""
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO error_telemetry (
                    user_id, error_type, error_message, error_traceback,
                    contract_length, engine_attempted, circuit_breaker_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, error_type, error_message, traceback,
                contract_length, engine_attempted, breaker_state
            ))
            
        logger.info(f"📉 Error logged: {error_type} - {error_message[:100]}")
        
    except Exception as e:
        logger.error(f"Failed to log error telemetry: {e}")


def log_performance_metric(
    metric_name: str,
    metric_value: float,
    engine: str = None,
    contract_length_bucket: str = None
):
    """Log performance metrics for optimization"""
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO performance_metrics (
                    metric_name, metric_value, engine, contract_length_bucket
                ) VALUES (?, ?, ?, ?)
            """, (metric_name, metric_value, engine, contract_length_bucket))
            
    except Exception as e:
        logger.error(f"Failed to log performance metric: {e}")


def log_user_action(
    user_id: str,
    action_type: str,
    metadata: Dict[str, Any] = None
):
    """Log user behavior for analytics"""
    try:
        metadata_json = json.dumps(metadata) if metadata else None
        
        with get_db() as conn:
            conn.execute("""
                INSERT INTO user_behavior (user_id, action_type, action_metadata)
                VALUES (?, ?, ?)
            """, (user_id, action_type, metadata_json))
            
    except Exception as e:
        logger.error(f"Failed to log user action: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS & REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def get_telemetry_summary(days: int = 7) -> Dict[str, Any]:
    """Get summary analytics from telemetry database"""
    try:
        with get_db() as conn:
            # Total analyses
            total = conn.execute("""
                SELECT COUNT(*) FROM analysis_telemetry
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            """, (days,)).fetchone()[0]
            
            # Average processing time
            avg_time = conn.execute("""
                SELECT AVG(processing_time_ms) FROM analysis_telemetry
                WHERE was_cached = 0 AND timestamp >= datetime('now', '-' || ? || ' days')
            """, (days,)).fetchone()[0]
            
            # Cache hit rate
            cached_count = conn.execute("""
                SELECT COUNT(*) FROM analysis_telemetry
                WHERE was_cached = 1 AND timestamp >= datetime('now', '-' || ? || ' days')
            """, (days,)).fetchone()[0]
            cache_rate = (cached_count / total * 100) if total > 0 else 0
            
            # Most common contract types
            contract_types = conn.execute("""
                SELECT contract_type, COUNT(*) as count
                FROM analysis_telemetry
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY contract_type
                ORDER BY count DESC
                LIMIT 5
            """, (days,)).fetchall()
            
            # Average risk score by engine
            risk_by_engine = conn.execute("""
                SELECT engine_used, AVG(risk_score) as avg_score
                FROM analysis_telemetry
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY engine_used
            """, (days,)).fetchall()
            
            return {
                'total_analyses': total,
                'avg_processing_time_ms': avg_time,
                'cache_hit_rate': cache_rate,
                'contract_types': [dict(row) for row in contract_types],
                'risk_by_engine': [dict(row) for row in risk_by_engine]
            }
            
    except Exception as e:
        logger.error(f"Failed to get telemetry summary: {e}")
        return {}


def export_training_data(output_path: str, limit: int = 10000):
    """Export telemetry data for model training"""
    try:
        with get_db() as conn:
            data = conn.execute("""
                SELECT 
                    contract_length, contract_type, risk_score, risk_level,
                    flagged_clause_count, critical_clauses, high_clauses,
                    processing_time_ms, engine_used
                FROM analysis_telemetry
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            import csv
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(data[0].keys())
                writer.writerows([tuple(row) for row in data])
            
            logger.info(f"✅ Exported {len(data)} records to {output_path}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to export training data: {e}")
        return False


# Initialize database on module import
init_telemetry_db()
