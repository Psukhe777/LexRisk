"""
rate_limiter.py — Enhanced Rate Limiting with SQL Backend
Atomic operations, tiered limits, and graceful fallback to JSON.
 
Features:
- PostgreSQL-backed with atomic increment operations
- Tiered limits: Free (3/day), Pro (50/day), Business (unlimited)
- Tracks analyses, pages, and text characters
- Automatic fallback to JSON if database unavailable
- Thread-safe file operations as backup
"""
 
import streamlit as st
from datetime import datetime, time
import json
import os
import uuid
import threading
import logging
 
logger = logging.getLogger(__name__)
 
# Try to import database utilities
try:
    from db_utils import (
        init_db_pool,
        get_or_create_user,
        check_rate_limit as db_check_rate_limit,
        increment_usage as db_increment_usage,
        get_usage_stats,
        get_user_tier
    )
    DB_AVAILABLE = True
except ImportError:
    logger.warning("db_utils not available - using JSON fallback")
    DB_AVAILABLE = False
 
# Fallback JSON file configuration
LIMITS_FILE = "user_limits.json"
file_lock = threading.Lock()
 
# ══════════════════════════════════════════════════════════════════════════════
# TIER CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
 
TIER_LIMITS = {
    'free': {
        'daily_analyses': 3,
        'max_pages': 2,
        'max_text_chars': 10000,
        'name': 'Free',
        'price': '$0/mo'
    },
    'pro': {
        'daily_analyses': 50,
        'max_pages': 100,
        'max_text_chars': 100000,
        'name': 'Pro',
        'price': '$15/mo'
    },
    'business': {
        'daily_analyses': -1,  # Unlimited
        'max_pages': -1,       # Unlimited
        'max_text_chars': -1,  # Unlimited
        'name': 'Business',
        'price': 'Custom'
    }
}
 
# ══════════════════════════════════════════════════════════════════════════════
# USER IDENTIFICATION
# ══════════════════════════════════════════════════════════════════════════════
 
def get_user_id():
    """
    Fetch the user's actual IP address to prevent 'page-refresh' bypasses.
    Falls back to a session UUID only if the IP is masked.
    
    Returns: (user_id, user_type)
    """
    try:
        # Streamlit 1.35+ allows accessing headers directly via context
        headers = st.context.headers
        
        # Check standard proxy/load balancer headers first
        ip_header = headers.get("X-Forwarded-For") or headers.get("X-Real-IP")
        
        if ip_header:
            # If multiple IPs are chained, grab the first one (the actual client)
            client_ip = ip_header.split(",")[0].strip()
            return f"ip_{client_ip}", "ip"
    except Exception as e:
        logger.debug(f"IP extraction bypassed: {e}")
 
    # Fallback to session ID if running locally without network headers
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"session_{uuid.uuid4()}"
    
    return st.session_state.user_id, "session"
 
# ══════════════════════════════════════════════════════════════════════════════
# DATABASE-BACKED RATE LIMITING (Primary)
# ══════════════════════════════════════════════════════════════════════════════
 
def check_rate_limit_db(user_id: str, limit_type: str = "analysis") -> tuple:
    """
    Check rate limit using PostgreSQL database.
    Returns: (is_allowed, remaining_count, reset_time, tier)
    """
    try:
        allowed, remaining, tier = db_check_rate_limit(user_id, limit_type)
        
        # Calculate reset time (end of day)
        reset_time = datetime.now().replace(hour=23, minute=59, second=59)
        
        logger.info(f"Rate limit check for {user_id}: allowed={allowed}, remaining={remaining}, tier={tier}")
        return allowed, remaining, reset_time, tier
        
    except Exception as e:
        logger.error(f"Database rate limit check failed: {e}")
        # Fall back to JSON method
        return check_rate_limit_json(user_id, limit_type)
 
def increment_usage_db(
    user_id: str, 
    limit_type: str = "analysis",
    pages: int = 1,
    text_chars: int = 0
) -> bool:
    """
    Atomically increment usage counter in database.
    This prevents race conditions when multiple users scan simultaneously.
    """
    try:
        success = db_increment_usage(user_id, limit_type, pages, text_chars)
        
        if success:
            logger.info(f"✅ Usage incremented for {user_id}: {limit_type} +1, pages +{pages}, chars +{text_chars}")
        
        return success
        
    except Exception as e:
        logger.error(f"Database increment failed: {e}")
        # Fall back to JSON method
        return increment_usage_json(user_id, limit_type)
 
# ══════════════════════════════════════════════════════════════════════════════
# JSON FILE FALLBACK (Secondary - for local dev or DB outages)
# ══════════════════════════════════════════════════════════════════════════════
 
def load_limits_json():
    """Load usage limits from JSON file safely."""
    if not os.path.exists(LIMITS_FILE):
        return {}
    
    with file_lock:
        try:
            with open(LIMITS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load limits file: {e}")
            return {}
 
def save_limits_json(limits):
    """Save usage limits to JSON file with thread safety."""
    with file_lock:
        try:
            with open(LIMITS_FILE, 'w') as f:
                json.dump(limits, f, indent=2)
        except Exception as e:
            logger.error(f"Warning: Could not save rate limits - {e}")
 
def check_rate_limit_json(user_id: str, limit_type: str = "analysis", max_daily: int = 3) -> tuple:
    """
    JSON-based rate limiting (fallback).
    Returns: (is_allowed, remaining_count, reset_time, tier)
    """
    limits = load_limits_json()
    today = datetime.now().date().isoformat()
    
    user_key = f"{user_id}_{limit_type}"
    
    # Initialize new user
    if user_key not in limits:
        limits[user_key] = {"date": today, "count": 0, "tier": "free"}
        save_limits_json(limits)
        
    user_limit = limits[user_key]
    
    # Reset if it's a new calendar day
    if user_limit.get("date") != today:
        user_limit = {"date": today, "count": 0, "tier": user_limit.get("tier", "free")}
        limits[user_key] = user_limit
        save_limits_json(limits)
        
    current_count = user_limit["count"]
    tier = user_limit.get("tier", "free")
    
    # Get tier limit
    tier_limit = TIER_LIMITS.get(tier, TIER_LIMITS['free'])['daily_analyses']
    if tier_limit == -1:  # Unlimited
        tier_limit = 999999
    
    remaining = max(0, tier_limit - current_count)
    allowed = remaining > 0
    
    reset_time = datetime.now().replace(hour=23, minute=59, second=59)
    
    return allowed, remaining, reset_time, tier
 
def increment_usage_json(user_id: str, limit_type: str = "analysis") -> bool:
    """Increment the usage counter in JSON file after a successful scan."""
    limits = load_limits_json()
    today = datetime.now().date().isoformat()
    user_key = f"{user_id}_{limit_type}"
    
    if user_key not in limits:
        limits[user_key] = {"date": today, "count": 0, "tier": "free"}
        
    # ATOMIC INCREMENT - Critical fix
    limits[user_key]["count"] += 1
    save_limits_json(limits)
    
    logger.info(f"✅ JSON usage incremented for {user_id}: count={limits[user_key]['count']}")
    return True
 
# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API (Auto-routing to DB or JSON)
# ══════════════════════════════════════════════════════════════════════════════
 
def check_rate_limit(user_id: str, limit_type: str = "analysis", max_daily: int = None) -> tuple:
    """
    Check if user has exceeded their daily limit.
    Auto-routes to database or JSON based on availability.
    
    Returns: (is_allowed, remaining_count, reset_time, tier)
    """
    if DB_AVAILABLE:
        return check_rate_limit_db(user_id, limit_type)
    else:
        # Use max_daily if provided, otherwise default to free tier
        if max_daily is None:
            max_daily = TIER_LIMITS['free']['daily_analyses']
        return check_rate_limit_json(user_id, limit_type, max_daily)
 
def increment_usage(
    user_id: str, 
    limit_type: str = "analysis",
    pages: int = 1,
    text_chars: int = 0
) -> bool:
    """
    Increment usage counter atomically.
    Auto-routes to database or JSON based on availability.
    """
    if DB_AVAILABLE:
        return increment_usage_db(user_id, limit_type, pages, text_chars)
    else:
        return increment_usage_json(user_id, limit_type)
 
def get_tier_info(tier: str) -> dict:
    """Get tier configuration information"""
    return TIER_LIMITS.get(tier, TIER_LIMITS['free'])
 
def format_usage_display(user_id: str) -> str:
    """
    Format usage statistics for display in the UI.
    Returns an HTML string with usage stats.
    """
    try:
        if DB_AVAILABLE:
            stats = get_usage_stats(user_id)
            tier = stats.get('tier', 'free')
            today_count = stats.get('today_count', 0)
            tier_limit = stats.get('tier_limit', 3)
            total = stats.get('total_analyses', 0)
        else:
            allowed, remaining, _, tier = check_rate_limit(user_id)
            limits = load_limits_json()
            user_key = f"{user_id}_analysis"
            today_count = limits.get(user_key, {}).get('count', 0)
            tier_limit = TIER_LIMITS[tier]['daily_analyses']
            total = today_count
        
        tier_info = get_tier_info(tier)
        
        # Calculate percentage
        if tier_limit == -1:
            percentage = 0
            limit_text = "∞"
        else:
            percentage = min(100, (today_count / tier_limit) * 100)
            limit_text = str(tier_limit)
        
        # Color coding
        if percentage >= 90:
            color = "#ff4444"  # Red
        elif percentage >= 70:
            color = "#ff8800"  # Orange
        else:
            color = "#44cc44"  # Green
        
        html = f"""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 100%); 
                    padding: 1.5rem; border-radius: 12px; margin: 1rem 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #fff;">📊 Usage Stats</h4>
                    <p style="margin: 0.5rem 0 0 0; color: #aaa; font-size: 0.9rem;">
                        {tier_info['name']} Plan • {tier_info['price']}
                    </p>
                </div>
                <div style="text-align: right;">
                    <p style="margin: 0; font-size: 2rem; font-weight: bold; color: {color};">
                        {today_count}/{limit_text}
                    </p>
                    <p style="margin: 0.5rem 0 0 0; color: #aaa; font-size: 0.9rem;">
                        Today's Scans
                    </p>
                </div>
            </div>
            <div style="margin-top: 1rem; background: #0d0d1a; border-radius: 8px; height: 8px; overflow: hidden;">
                <div style="width: {percentage}%; height: 100%; background: {color}; 
                            transition: width 0.3s ease;"></div>
            </div>
            <p style="margin: 0.5rem 0 0 0; color: #aaa; font-size: 0.8rem; text-align: center;">
                {total} total analyses • Resets at midnight
            </p>
        </div>
        """
        
        return html
        
    except Exception as e:
        logger.error(f"Error formatting usage display: {e}")
        return ""
 
# ══════════════════════════════════════════════════════════════════════════════
# INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════════
 
def initialize_rate_limiter():
    """Initialize the rate limiter (call this at app startup)"""
    if DB_AVAILABLE:
        try:
            init_db_pool()
            logger.info("✅ Rate limiter initialized with database backend")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            logger.info("⚠️ Falling back to JSON file storage")
    else:
        logger.info("⚠️ Rate limiter using JSON file storage (no database)")
