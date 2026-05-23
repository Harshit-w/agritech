"""
api/rate_limit.py
Rate limiting protection to prevent API spam
"""

import time
import logging
from functools import wraps
from flask import current_app, request, jsonify

log = logging.getLogger(__name__)

# ── In-memory rate limit tracking ──────────────────────────────────────────────
# Format: {user_identifier: {endpoint: last_call_timestamp}}
_rate_limit_tracker = {}

# ── Configuration ──────────────────────────────────────────────────────────────
# Time window in seconds between allowed requests
DEFAULT_RATE_LIMIT = 2.0  # seconds
ENDPOINTS_CONFIG = {
    "chat_stream":      0.3,   # Allow chat messages more frequently (333ms = ~3 msgs/sec)
    "chat":             0.3,   # Non-streaming fallback
    "analyse_image":    3.0,   # Image analysis is expensive
    "predict":          1.0,   # ML predictions need some throttling  
    "sensors":          1.0,   # Read-only (GET) won't be rate limited anyway
    "weather":          1.0,   # Read-only (GET) won't be rate limited anyway
}


def get_user_identifier():
    """
    Extract user identifier from request.
    Priority: session_id → IP address → 'anonymous'
    """
    data = request.get_json() or {}
    session_id = data.get("session_id")
    if session_id:
        return f"session_{session_id}"
    return f"ip_{request.remote_addr}"


def allow_request(user_id, endpoint="default"):
    """
    Check if user can make a request (rate limit check).
    Returns: (is_allowed: bool, retry_after: float|None)
    """
    now = time.time()
    rate_limit = ENDPOINTS_CONFIG.get(endpoint, DEFAULT_RATE_LIMIT)
    
    if user_id not in _rate_limit_tracker:
        _rate_limit_tracker[user_id] = {}
    
    user_endpoints = _rate_limit_tracker[user_id]
    last_call = user_endpoints.get(endpoint, 0)
    
    time_since_last = now - last_call
    
    if time_since_last < rate_limit:
        retry_after = rate_limit - time_since_last
        return False, retry_after
    
    # Update last call timestamp
    user_endpoints[endpoint] = now
    return True, None


def rate_limit(endpoint_name=None, skip_get=True):
    """
    Decorator to add rate limiting to Flask routes.
    Usage: @rate_limit("chat_stream")
    skip_get: If True, allow unlimited GET requests (safe read-only operations)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting in test mode to keep unit tests deterministic.
            if current_app.config.get("TESTING"):
                return f(*args, **kwargs)

            # Skip rate limiting for GET requests (read-only, safe)
            if skip_get and request.method == "GET":
                return f(*args, **kwargs)
            
            endpoint = endpoint_name or f.__name__
            user_id = get_user_identifier()
            
            is_allowed, retry_after = allow_request(user_id, endpoint)
            
            if not is_allowed:
                log.warning(f"Rate limit exceeded for {user_id} on {endpoint} (retry in {retry_after:.2f}s)")
                return jsonify({
                    "error": "Too many requests. Please wait before trying again.",
                    "retry_after": round(retry_after, 2),
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def cleanup_old_records(max_age=3600):
    """
    Remove old rate limit records (older than max_age seconds).
    Call periodically to prevent memory bloat.
    """
    now = time.time()
    expired_users = []
    
    for user_id, endpoints in _rate_limit_tracker.items():
        # Keep only recent endpoints
        for endpoint in list(endpoints.keys()):
            if now - endpoints[endpoint] > max_age:
                del endpoints[endpoint]
        
        # Remove user if no endpoints tracked
        if not endpoints:
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del _rate_limit_tracker[user_id]
        
    log.debug(f"Cleaned up {len(expired_users)} expired rate limit records")
