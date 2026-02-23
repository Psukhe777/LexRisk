import streamlit as st
from datetime import datetime
import json
import os
import uuid

LIMITS_FILE = "user_limits.json"

def get_user_id():
    """Generate a simple user ID based on session"""
    if 'user_id' not in st.session_state:
        # Create a unique ID for this browser tab session
        st.session_state.user_id = str(uuid.uuid4())
    return st.session_state.user_id

def load_limits():
    """Load usage limits from file"""
    if not os.path.exists(LIMITS_FILE):
        return {}
    try:
        with open(LIMITS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        # If the file is locked or corrupted, return an empty dict to prevent a crash
        return {}

def save_limits(limits):
    """Save usage limits to file gracefully"""
    try:
        with open(LIMITS_FILE, 'w') as f:
            json.dump(limits, f)
    except Exception as e:
        print(f"Warning: Could not save rate limits - {e}")

def check_rate_limit(user_id, limit_type="analysis", max_daily=2):
    """Check if user has exceeded their daily limit."""
    limits = load_limits()
    today = datetime.now().date().isoformat()
    
    user_key = f"{user_id}_{limit_type}"
    
    if user_key not in limits:
        limits[user_key] = {"date": today, "count": 0}
        
    user_limit = limits[user_key]
    
    # Reset if new day
    if user_limit["date"] != today:
        user_limit = {"date": today, "count": 0}
        limits[user_key] = user_limit
        
    current_count = user_limit["count"]
    remaining = max_daily - current_count
    allowed = remaining > 0
    
    reset_time = datetime.now().replace(hour=23, minute=59, second=59)
    return allowed, remaining, reset_time

def increment_usage(user_id, limit_type="analysis"):
    """Increment usage counter for user"""
    limits = load_limits()
    today = datetime.now().date().isoformat()
    user_key = f"{user_id}_{limit_type}"
    
    if user_key not in limits:
        limits[user_key] = {"date": today, "count": 0}
        
    limits[user_key]["count"] += 1
    save_limits(limits)
