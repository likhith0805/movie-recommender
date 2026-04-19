from __future__ import annotations

import re
from flask import Blueprint, jsonify, request

from backend.utils import current_user_id
from models.recommender import CollaborativeFilteringRecommender


chat_bp = Blueprint("chat_bp", __name__)
_recommender = CollaborativeFilteringRecommender()


GENRES = [
    "action",
    "adventure",
    "animation",
    "comedy",
    "crime",
    "documentary",
    "drama",
    "fantasy",
    "film-noir",
    "horror",
    "music",
    "mystery",
    "romance",
    "sci-fi",
    "thriller",
    "war",
    "western",
]


def _extract_user_ids(text: str) -> list[int]:
    # Very simple rule: grab all numbers from the message.
    # This is beginner-friendly and works for "user 12" style inputs.
    nums = re.findall(r"\d+", text or "")
    out: list[int] = []
    for n in nums:
        try:
            out.append(int(n))
        except ValueError:
            continue
    # Deduplicate while keeping order.
    seen = set()
    deduped = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped


@chat_bp.route("/api/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json(force=True) or {}
    query = str(data.get("query", "")).strip()

    if not query:
        return jsonify({"reply": "Ask me something like: 'Suggest movies for me and my friend'."}), 400

    session_uid = current_user_id()
    requested_user_ids = data.get("user_ids")

    # 1) Determine genre intent (optional filter)
    query_lower = query.lower()
    genre = None
    for g in GENRES:
        if g in query_lower:
            genre = g
            break

    # 2) Determine group intent
    wants_group = any(
        kw in query_lower for kw in ["friend", "friends", "together", "group", "both", "me and"]
    )

    # 3) Determine user ids for recommendations
    if requested_user_ids is not None:
        try:
            user_ids = [int(x) for x in requested_user_ids]
        except (TypeError, ValueError):
            user_ids = [session_uid] if session_uid is not None else []
    else:
        if session_uid is None:
            # Without login, we can still recommend popular movies.
            user_ids = []
        else:
            user_ids = [session_uid]

    # If message includes numbers, treat them as extra group user ids.
    extra_ids = _extract_user_ids(query)
    for x in extra_ids:
        if x not in user_ids:
            user_ids.append(x)

    # If we want group but only have one id, we still answer with personal recs.
    reply_prefix = ""
    if wants_group and len(user_ids) == 1:
        reply_prefix = (
            "I can recommend movies for you and your friend. "
            "To make it truly group-based, include your friend's user id in your message "
            "(example: '... user 42').\n\n"
        )

    if not user_ids:
        # Not logged in: give popular recommendations.
        items = _recommender.recommend_popular(genre=genre, top_n=5)
        return jsonify(
            {
                "reply": reply_prefix + "Here are some popular picks:",
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

    mode = "personal" if len(user_ids) == 1 else "group"
    if mode == "personal":
        items = _recommender.recommend_personal(user_id=user_ids[0], genre=genre, top_n=5)
    else:
        items = _recommender.recommend_group(user_ids=user_ids, genre=genre, top_n=5)

    reply = reply_prefix + ("Here are recommendations based on your group tastes." if mode == "group" else "Here are recommendations for you.")

    return jsonify(
        {
            "reply": reply,
            "mode": mode,
            "recommendations": [
                {
                    "movie_id": it.movie_id,
                    "title": it.title,
                    "genre": it.genre,
                    "score": it.score,
                    "why": it.why,
                }
                for it in items
            ],
        }
    )

