from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.utils import current_user_id
from models import db


movies_bp = Blueprint("movies_bp", __name__)


@movies_bp.route("/api/movies", methods=["GET"])
def list_movies():
    user_id = current_user_id()
    query = request.args.get("query", default=None, type=str)
    genre = request.args.get("genre", default=None, type=str)
    limit = request.args.get("limit", default=24, type=int)
    limit = max(1, min(limit, 50))

    movies = db.get_movies_with_ratings(
        user_id=user_id,
        query=query,
        genre=genre,
        limit=limit,
    )
    return jsonify({"movies": movies})


@movies_bp.route("/api/movies/<int:movie_id>", methods=["GET"])
def movie_details(movie_id: int):
    user_id = current_user_id()
    movie = db.get_movie_with_ratings(user_id=user_id, movie_id=movie_id)
    if movie is None:
        return jsonify({"error": "movie_not_found"}), 404
    return jsonify({"movie": movie})

