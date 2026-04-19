from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.utils import current_user_id, login_required_json
from models import db


ratings_bp = Blueprint("ratings_bp", __name__)


@ratings_bp.route("/api/ratings", methods=["POST"])
@login_required_json
def add_rating():
    data = request.get_json(force=True) or {}
    movie_id = data.get("movie_id")
    rating = data.get("rating")

    if movie_id is None or rating is None:
        return jsonify({"error": "missing_movie_id_or_rating"}), 400

    try:
        movie_id_int = int(movie_id)
        rating_int = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_types"}), 400

    if rating_int < 1 or rating_int > 5:
        return jsonify({"error": "rating_must_be_1_to_5"}), 400

    if db.get_movie(movie_id_int) is None:
        return jsonify({"error": "movie_not_found"}), 404

    user_id = current_user_id()
    assert user_id is not None
    db.upsert_rating(user_id=user_id, movie_id=movie_id_int, rating=rating_int)
    return jsonify({"success": True})


@ratings_bp.route("/api/feedback", methods=["POST"])
@login_required_json
def add_feedback():
    data = request.get_json(force=True) or {}
    movie_id = data.get("movie_id")
    feedback = str(data.get("feedback", "")).strip().lower()

    if movie_id is None or not feedback:
        return jsonify({"error": "missing_movie_id_or_feedback"}), 400

    try:
        movie_id_int = int(movie_id)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_movie_id"}), 400

    if db.get_movie(movie_id_int) is None:
        return jsonify({"error": "movie_not_found"}), 404

    if feedback == "like":
        rating_int = 5
    elif feedback == "dislike":
        rating_int = 1
    else:
        return jsonify({"error": "feedback_must_be_like_or_dislike"}), 400

    user_id = current_user_id()
    assert user_id is not None
    db.upsert_rating(user_id=user_id, movie_id=movie_id_int, rating=rating_int)
    return jsonify({"success": True})

