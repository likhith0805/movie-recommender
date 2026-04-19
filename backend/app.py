from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

# When running with `python backend/app.py`, Python may not include the project root
# on `sys.path`, so `import backend` could fail. This makes it robust.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config
from backend.utils import current_user_id
from models.db import get_user_by_id
from routes.auth_routes import auth_bp
from routes.movies_routes import movies_bp
from routes.ratings_routes import ratings_bp
from routes.recommendations_routes import reco_bp
from routes.chatbot_routes import chat_bp


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "static"


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = Config.SECRET_KEY

    # API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(movies_bp)
    app.register_blueprint(ratings_bp)
    app.register_blueprint(reco_bp)
    app.register_blueprint(chat_bp)

    @app.get("/")
    def index():
        uid = current_user_id()
        if uid is None:
            return redirect(url_for("auth_page_login"))
        return redirect(url_for("page_browse"))

    @app.get("/login")
    def auth_page_login():
        uid = current_user_id()
        if uid is not None:
            return redirect(url_for("page_browse"))
        return render_template("login.html")

    @app.get("/browse")
    def page_browse():
        uid = current_user_id()
        if uid is None:
            return redirect(url_for("auth_page_login"))
        return render_template("browse.html")

    @app.get("/movie/<int:movie_id>")
    def page_movie_details(movie_id: int):
        uid = current_user_id()
        if uid is None:
            return redirect(url_for("auth_page_login"))
        return render_template("movie_details.html", movie_id=movie_id)

    @app.get("/dashboard")
    def page_dashboard():
        uid = current_user_id()
        if uid is None:
            return redirect(url_for("auth_page_login"))
        return render_template("dashboard.html")

    @app.get("/api/me")
    def me():
        uid = current_user_id()
        if uid is None:
            return jsonify({"logged_in": False})
        user = get_user_by_id(uid)
        if user is None:
            return jsonify({"logged_in": False})
        return jsonify({"logged_in": True, "user_id": int(user["id"]), "username": user["username"]})

    return app


app = create_app()


if __name__ == "__main__":
    # Initialize database if it doesn't exist (important for production)
    if not os.path.exists(Config.DATABASE_PATH):
        print("Database not found. Initializing...")
        from backend.init_db import main as init_db_main
        init_db_main()
        print("Database initialized!")
    
    # Helpful for local development.
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=debug)

