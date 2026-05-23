"""api/auth.py — Optional token auth and role metadata endpoints."""

from flask import Blueprint, jsonify, request
from services.auth import current_user, get_users, issue_token, require_roles

bp = Blueprint("auth", __name__)


@bp.route("/auth/login", methods=["POST"])
def login():
    """POST /api/auth/login — issue bearer token for configured users."""
    data = request.get_json() or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    users = get_users()
    user = users.get(username)
    if not user or user.get("password") != password:
        return jsonify({"error": "invalid_credentials"}), 401

    role = str(user.get("role", "viewer"))
    token = issue_token(username, role)
    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "username": username,
        "role": role,
    })


@bp.route("/auth/me", methods=["GET"])
@require_roles("viewer", "agronomist", "admin")
def me():
    """GET /api/auth/me — return current identity when auth is enabled."""
    return jsonify({"user": current_user()})


@bp.route("/auth/roles", methods=["GET"])
def roles():
    """GET /api/auth/roles — available role names for client-side UX."""
    return jsonify({"roles": ["viewer", "agronomist", "admin"]})
