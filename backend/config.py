import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    # Flask session secret key (change in production).
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

    # SQLite database path.
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "backend" / "data" / "movies.db")
    )

    # MovieLens download/cache directory.
    MOVIELENS_DIR = os.environ.get(
        "MOVIELENS_DIR", str(BASE_DIR / "backend" / "data" / "movielens")
    )

