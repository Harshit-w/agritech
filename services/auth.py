"""services/auth.py
Lightweight signed bearer tokens with optional RBAC enforcement.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from functools import wraps
from flask import current_app, g, jsonify, request


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _settings() -> dict:
    cfg = current_app.config
    return {
        "enabled": bool(cfg.get("AUTH_ENABLED", False)),
        "secret": str(cfg.get("SECRET_KEY", "change-me")),
        "ttl_s": int(cfg.get("AUTH_TOKEN_TTL_HOURS", 12)) * 3600,
        "users_json": str(cfg.get("AUTH_USERS_JSON", "")),
    }


def get_users() -> dict:
    """Load user map from config/env. Format: {username: {password, role}}."""
    raw = _settings()["users_json"] or os.getenv("AUTH_USERS_JSON", "")
    if raw:
        try:
            users = json.loads(raw)
            if isinstance(users, dict):
                return users
        except Exception:
            pass
    return {
        "admin": {"password": "admin123", "role": "admin"},
        "agri": {"password": "agri123", "role": "agronomist"},
        "viewer": {"password": "view123", "role": "viewer"},
    }


def issue_token(username: str, role: str) -> str:
    """Issue a signed bearer token with expiry."""
    s = _settings()
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + s["ttl_s"],
    }
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(s["secret"].encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def verify_token(token: str) -> tuple[dict | None, str | None]:
    """Verify token integrity and expiry. Returns (claims, error)."""
    s = _settings()
    parts = token.split(".")
    if len(parts) != 3:
        return None, "invalid_token"

    h, p, sig = parts
    signing_input = f"{h}.{p}".encode("ascii")
    expected = hmac.new(s["secret"].encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        got = _b64url_decode(sig)
    except Exception:
        return None, "invalid_signature"

    if not hmac.compare_digest(expected, got):
        return None, "invalid_signature"

    try:
        claims = json.loads(_b64url_decode(p).decode("utf-8"))
    except Exception:
        return None, "invalid_payload"

    if int(claims.get("exp", 0)) < int(time.time()):
        return None, "token_expired"

    return claims, None


def require_roles(*allowed_roles):
    """Require bearer auth and optional role checks when AUTH_ENABLED=true."""

    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _settings()["enabled"]:
                return func(*args, **kwargs)

            authz = request.headers.get("Authorization", "")
            if not authz.startswith("Bearer "):
                return jsonify({"error": "missing_bearer_token"}), 401

            token = authz.split(" ", 1)[1].strip()
            claims, err = verify_token(token)
            if err:
                return jsonify({"error": err}), 401

            g.current_user = {
                "username": claims.get("sub", "unknown"),
                "role": claims.get("role", "viewer"),
            }

            if allowed_roles and g.current_user["role"] not in allowed_roles:
                return jsonify({"error": "forbidden", "required_roles": list(allowed_roles)}), 403

            return func(*args, **kwargs)

        return wrapper

    return deco


def current_user() -> dict:
    return getattr(g, "current_user", {"username": "anonymous", "role": "viewer"})