"""
db_utils.py — PostgreSQL database utilities for LexRisk
Handles user tracking, rate limiting, caching, and analytics with atomic operations.

Features:
- Connection pooling for performance
- Atomic increment operations (no race conditions)
- Graceful fallback to JSON if DB unavailable
- Automatic migration and table creation
"""

import os
import json
import hashlib
import logging
from datetime import datetime, date
from typing import Optional, Tuple, Dict, Any
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONNECTION POOL
# ══════════════════════════════════════════════════════════════════════════════

_connection_pool = None

def init_db_pool(database_url: Optional[str] = None):
    """Initialize connection pool (call once at startup)"""
    global _connection_pool
    
    if _connection_pool is not None:
        return
    
    db_url = database_url or os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.warning("No DATABASE_URL found - falling back to JSON file storage")
        return None
    
    try:
        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=db_url
        )
        logger.info("✅ Database connection pool initialized")
        
        # Run schema creation on first connection
        _ensure_schema_exists()
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize database pool: {e}")
        _connection_pool = None

@contextmanager
def get_db_connection():
    """Context manager for database connections with auto-commit"""
    if _connection_pool is None:
        yield None
        return
    
    conn = None
    try:
        conn = _connection_pool.getconn()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            _connection_pool.putconn(conn)

def _ensure_schema_exists():
    """Create tables if they don't exist"""
    with get_db_connection() as conn:
        if conn is None:
            return
        
        with conn.cursor() as cur:
            # Check if users table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users'
                );
            """)
            
            if not cur.fetchone()[0]:
                logger.info("Creating database schema...")
                schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
                
                if os.path.exists(schema_path):
                    with open(schema_path, 'r') as f:
                        cur.execute(f.read())
                    logger.info("✅ Schema created successfully")
                else:
                    logger.warning("schema.sql not found - run manual migration")

# ══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_user(user_id: str, user_type: str = 'ip', tier: str = 'free') -> bool:
    """Ensure user exists in database, create if not"""
    with get_db_connection() as conn:
        if conn is None:
            return False
        
        with conn.cursor() as cur:
            cur.execute(
                "SELECT get_or_create_user(%s, %s, %s);",
                (user_id, user_type, tier)
            )
            return True

def get_user_tier(user_id: str) -> str:
    """Get user's subscription tier"""
    with get_db_connection() as conn:
        if conn is None:
            return 'free'
        
        with conn.cursor() as cur:
            cur.execute("SELECT tier FROM users WHERE user_id = %s;", (user_id,))
            result = cur.fetchone()
            return result[0] if result else 'free'

def upgrade_user_tier(user_id: str, new_tier: str) -> bool:
    """Upgrade user to a new tier (pro or business)"""
    with get_db_connection() as conn:
        if conn is None:
            return False
        
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET tier = %s WHERE user_id = %s;",
                (new_tier, user_id)
            )
            return cur.rowcount > 0

# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMITING
# ══════════════════════════════════════════════════════════════════════════════

def check_rate_limit(user_id: str, limit_type: str = "analysis") -> Tuple[bool, int, str]:
    """
    Check if user has exceeded their daily limit.
    Returns: (is_allowed, remaining_count, tier)
    """
    with get_db_connection() as conn:
        if conn is None:
            # Fallback to basic limit if DB unavailable
            return (True, 3, 'free')
        
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM check_daily_limit(%s, %s);",
                (user_id, limit_type)
            )
            result = cur.fetchone()
            
            if result:
                allowed, remaining, tier = result
                # Business tier returns -1 for unlimited
                if remaining == -1:
                    remaining = 999999
                return (allowed, remaining, tier)
            
            return (True, 3, 'free')

def increment_usage(
    user_id: str, 
    limit_type: str = "analysis",
    pages: int = 1,
    text_chars: int = 0
) -> bool:
    """
    Atomically increment usage counter.
    This is CRITICAL for preventing race conditions.
    """
    with get_db_connection() as conn:
        if conn is None:
            return False
        
        with conn.cursor() as cur:
            cur.execute(
                "SELECT increment_usage(%s, %s, %s, %s);",
                (user_id, limit_type, pages, text_chars)
            )
            return True

def get_usage_stats(user_id: str) -> Dict[str, Any]:
    """Get detailed usage statistics for a user"""
    with get_db_connection() as conn:
        if conn is None:
            return {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    u.tier,
                    u.total_analyses,
                    u.total_pages_processed,
                    u.total_text_chars,
                    COALESCE(ul.count, 0) as today_count,
                    tl.daily_analyses as tier_limit
                FROM users u
                LEFT JOIN usage_limits ul ON u.user_id = ul.user_id 
                    AND ul.date = CURRENT_DATE 
                    AND ul.limit_type = 'analysis'
                LEFT JOIN tier_limits tl ON u.tier = tl.tier
                WHERE u.user_id = %s;
            """, (user_id,))
            
            result = cur.fetchone()
            return dict(result) if result else {}

# ══════════════════════════════════════════════════════════════════════════════
# CACHING SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def get_contract_hash(contract_text: str) -> str:
    """Generate SHA256 hash of contract text"""
    return hashlib.sha256(contract_text.encode('utf-8')).hexdigest()

def get_cached_analysis(contract_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached analysis result if it exists"""
    with get_db_connection() as conn:
        if conn is None:
            return None
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE analysis_cache
                SET hit_count = hit_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE contract_hash = %s
                RETURNING analysis_result, engine_used;
            """, (contract_hash,))
            
            result = cur.fetchone()
            
            if result:
                logger.info(f"✅ Cache HIT for contract {contract_hash[:8]}...")
                return dict(result)
            
            logger.info(f"❌ Cache MISS for contract {contract_hash[:8]}...")
            return None

def cache_analysis(
    contract_hash: str,
    contract_length: int,
    risk_score: int,
    risk_level: str,
    analysis_result: Dict[str, Any],
    engine_used: str
) -> bool:
    """Store analysis result in cache"""
    with get_db_connection() as conn:
        if conn is None:
            return False
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analysis_cache 
                (contract_hash, contract_length, risk_score, risk_level, analysis_result, engine_used)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (contract_hash) DO UPDATE
                SET hit_count = analysis_cache.hit_count + 1,
                    last_accessed = CURRENT_TIMESTAMP;
            """, (contract_hash, contract_length, risk_score, risk_level, 
                  json.dumps(analysis_result), engine_used))
            
            return True

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS TRACKING
# ══════════════════════════════════════════════════════════════════════════════

def log_analysis(
    user_id: str,
    contract_hash: str,
    contract_length: int,
    page_count: int,
    risk_score: int,
    risk_level: str,
    engine_used: str,
    was_cached: bool,
    processing_time_ms: int
) -> bool:
    """Log an analysis request for analytics"""
    with get_db_connection() as conn:
        if conn is None:
            return False
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analysis_history 
                (user_id, contract_hash, contract_length, page_count, risk_score, 
                 risk_level, engine_used, was_cached, processing_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (user_id, contract_hash, contract_length, page_count, risk_score,
                  risk_level, engine_used, was_cached, processing_time_ms))
            
            return True

def track_redlined_clause(
    clause_category: str,
    clause_severity: str,
    clause_text: str,
    contract_hash: str
) -> bool:
    """Track a detected predatory clause for analytics"""
    with get_db_connection() as conn:
        if conn is None:
            return False
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO redlined_clauses 
                (clause_category, clause_severity, clause_text, contract_hash)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (clause_category, clause_severity, clause_text, contract_hash))
            
            return True

# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

def get_cache_stats() -> Dict[str, Any]:
    """Get cache performance statistics"""
    with get_db_connection() as conn:
        if conn is None:
            return {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_cached,
                    SUM(hit_count) as total_hits,
                    AVG(hit_count) as avg_hits_per_entry,
                    MAX(last_accessed) as last_cache_hit
                FROM analysis_cache;
            """)
            
            result = cur.fetchone()
            return dict(result) if result else {}

def get_daily_stats(days: int = 7) -> list:
    """Get daily usage statistics for the past N days"""
    with get_db_connection() as conn:
        if conn is None:
            return []
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM daily_usage_summary
                LIMIT %s;
            """, (days,))
            
            return [dict(row) for row in cur.fetchall()]

def get_tier_stats() -> list:
    """Get tier distribution statistics"""
    with get_db_connection() as conn:
        if conn is None:
            return []
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM tier_distribution;")
            return [dict(row) for row in cur.fetchall()]

# ══════════════════════════════════════════════════════════════════════════════
# JSON FALLBACK (if database unavailable)
# ══════════════════════════════════════════════════════════════════════════════

FALLBACK_FILE = "lexrisk_fallback.json"

def _load_fallback_data() -> dict:
    """Load fallback JSON data"""
    if os.path.exists(FALLBACK_FILE):
        try:
            with open(FALLBACK_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"users": {}, "cache": {}}

def _save_fallback_data(data: dict):
    """Save fallback JSON data"""
    try:
        with open(FALLBACK_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save fallback data: {e}")
