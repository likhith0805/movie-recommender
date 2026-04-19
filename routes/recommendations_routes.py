from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.utils import current_user_id
from models.recommender import CollaborativeFilteringRecommender


reco_bp = Blueprint("reco_bp", __name__)

_recommender = CollaborativeFilteringRecommender()


@reco_bp.route("/api/recommendations", methods=["POST"])
def recommendations():
    data = request.get_json(force=True) or {}

    requested_user_ids = data.get("user_ids")
    genre = data.get("genre")
    top_n = data.get("top_n", 5)

    try:
        top_n_int = int(top_n)
    except (TypeError, ValueError):
        top_n_int = 5
    top_n_int = max(1, min(top_n_int, 10))

    if requested_user_ids is None:
        uid = current_user_id()
        if uid is None:
            return jsonify({"error": "login_required"}), 401
        user_ids = [uid]
    else:
        if not isinstance(requested_user_ids, list) or not requested_user_ids:
            return jsonify({"error": "user_ids_must_be_a_non_empty_list"}), 400
        try:
            user_ids = [int(x) for x in requested_user_ids]
        except (TypeError, ValueError):
            return jsonify({"error": "user_ids_must_be_integers"}), 400

    mode = "personal" if len(user_ids) == 1 else "group"

    if mode == "personal":
        items = _recommender.recommend_personal(user_id=user_ids[0], genre=genre, top_n=top_n_int)
    else:
        items = _recommender.recommend_group(user_ids=user_ids, genre=genre, top_n=top_n_int)

    return jsonify(
        {
            "mode": mode,
            "recommendations": [
                {
                    "movie_id": it.movie_id,
                    "title": it.title,
                    "genre": it.genre,
                    "score": it.score,
                    "avg_rating": it.avg_rating,
                    "why": it.why,
                }
                for it in items
            ],
        }
    )

