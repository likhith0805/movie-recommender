from __future__ import annotations

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from backend.utils import current_user_id
from models.db import create_user, get_user_by_username


auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if len(username) < 3:
        return jsonify({"error": "username_too_short"}), 400
    if len(password) < 4:
        return jsonify({"error": "password_too_short"}), 400

    existing = get_user_by_username(username)
    if existing is not None:
        return jsonify({"error": "username_taken"}), 409

    password_hash = generate_password_hash(password)
    user_id = create_user(username=username, password_hash=password_hash)

    session["user_id"] = user_id
    return jsonify({"success": True, "user_id": user_id, "username": username})


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    user = get_user_by_username(username)
    if user is None:
        return jsonify({"error": "invalid_credentials"}), 401

    if not check_password_hash(user["password"], password):
        return jsonify({"error": "invalid_credentials"}), 401

    session["user_id"] = int(user["id"])
    return jsonify({"success": True, "user_id": int(user["id"]), "username": user["username"]})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    # Clear user session.
    session.pop("user_id", None)
    return jsonify({"success": True})

