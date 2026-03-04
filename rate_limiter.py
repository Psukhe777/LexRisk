import streamlit as st
from datetime import datetime
import json
import os
import uuid
import threading

LIMITS_FILE = "user_limits.json"
# Use a thread lock to prevent file corruption when multiple users scan at the exact same time
file_lock = threading.Lock() 

def get_user_id():
    """
    Fetch the user's actual IP address to prevent 'page-refresh' bypasses.
    Falls back to a session UUID only if the IP is masked.
    """
    try:
        # Streamlit 1.35+ allows accessing headers directly via context
        headers = st.context.headers
        
        # Check standard proxy/load balancer headers first
        ip_header = headers.get("X-Forwarded-For") or headers.get("X-Real-IP")
        
        if ip_header:
            # If multiple IPs are chained, grab the first one (the actual client)
            client_ip = ip_header.split(",")[0].strip()
            return f"ip_{client_ip}"
    except Exception as e:
        print(f"IP extraction bypassed: {e}")

    # Fallback to session ID if running locally without network headers
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"session_{uuid.uuid4()}"
    return st.session_state.user_id

def load_limits():
    """Load usage limits from file safely."""
    if not os.path.exists(LIMITS_FILE):
        return {}
    
    with file_lock:
        try:
            with open(LIMITS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            # If the file is corrupted during a reboot, return an empty dict
            return {}

def save_limits(limits):
    """Save usage limits to file with thread safety."""
    with file_lock:
        try:
            with open(LIMITS_FILE, 'w') as f:
                json.dump(limits, f)
        except Exception as e:
            print(f"Warning: Could not save rate limits - {e}")

def check_rate_limit(user_id, limit_type="analysis", max_daily=3):
    """
    Check if user has exceeded their daily limit.
    Returns: (is_allowed, remaining_scans, reset_time)
    """
    limits = load_limits()
    today = datetime.now().date().isoformat()
    
    user_key = f"{user_id}_{limit_type}"
    
    # Initialize new user
    if user_key not in limits:
        limits[user_key] = {"date": today, "count": 0}
        
    user_limit = limits[user_key]
    
    # Reset if it's a new calendar day
    if user_limit.get("date") != today:
        user_limit = {"date": today, "count": 0}
        limits[user_key] = user_limit
        
    current_count = user_limit["count"]
    remaining = max(0, max_daily - current_count)
    allowed = remaining > 0
    
    reset_time = datetime.now().replace(hour=23, minute=59, second=59)
    return allowed, remaining, reset_time

def increment_usage(user_id, limit_type="analysis"):
    """Increment the usage counter for the user after a successful scan."""
    limits = load_limits()
    today = datetime.now().date().isoformat()
    user_key = f"{user_id}_{limit_type}"
    
    if user_key not in limits:
        limits[user_key] = {"date": today, "count": 0}
        
    limits[user_key]["count"] += 2
    save_limits(limits)
