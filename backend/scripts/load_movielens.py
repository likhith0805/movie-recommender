from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

import pandas as pd
import requests

from backend.init_db import init_db
from backend.config import Config

import sqlite3
from werkzeug.security import generate_password_hash


DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"


def download_if_needed(url: str, dest_zip: Path) -> None:
    if dest_zip.exists():
        return

    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading MovieLens dataset from: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    dest_zip.write_bytes(r.content)
    print(f"Downloaded to: {dest_zip}")


def extract_zip(dest_zip: Path, extract_dir: Path) -> Path:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip) as zf:
        zf.extractall(extract_dir)

    extracted_root = extract_dir / "ml-latest-small"
    if not extracted_root.exists():
        # Fallback: look for movies.csv in extracted tree.
        return extract_dir
    return extracted_root


def main():
    parser = argparse.ArgumentParser(description="Load MovieLens ratings into SQLite.")
    parser.add_argument("--download", action="store_true", help="Download dataset if missing.")
    parser.add_argument("--max-users", type=int, default=0, help="0 = all users.")
    parser.add_argument("--max-movies", type=int, default=0, help="0 = all movies.")
    parser.add_argument(
        "--max-ratings", type=int, default=0, help="0 = all ratings (after optional user/movie filters)."
    )
    args = parser.parse_args()

    init_db()

    movielens_dir = Path(Config.MOVIELENS_DIR)
    zip_path = movielens_dir / "ml-latest-small.zip"
    extracted_dir = movielens_dir

    if args.download:
        download_if_needed(DATASET_URL, zip_path)

    if not zip_path.exists() and not (extracted_dir / "ml-latest-small" / "movies.csv").exists():
        raise SystemExit(
            "Dataset not found. Run with --download, or manually place ml-latest-small/movies.csv and ratings.csv in the movielens dir."
        )

    dataset_root = extracted_dir / "ml-latest-small"
    if not dataset_root.exists():
        dataset_root = extract_zip(zip_path, extracted_dir)

    movies_csv = dataset_root / "movies.csv"
    ratings_csv = dataset_root / "ratings.csv"

    if not movies_csv.exists() or not ratings_csv.exists():
        raise SystemExit("Could not locate movies.csv/ratings.csv after extraction.")

    print("Loading CSVs into pandas...")
    movies_df = pd.read_csv(movies_csv)
    ratings_df = pd.read_csv(ratings_csv)

    # Optional limits for faster experimentation.
    if args.max_movies and args.max_movies > 0:
        movies_df = movies_df.head(args.max_movies)

    if args.max_users and args.max_users > 0:
        ratings_df = ratings_df[ratings_df["userId"].isin(ratings_df["userId"].unique()[: args.max_users])]

    # Keep only ratings that reference movies we loaded.
    movies_ids = set(int(x) for x in movies_df["movieId"].tolist())
    ratings_df = ratings_df[ratings_df["movieId"].isin(movies_ids)]

    # Map genre: store primary genre (first token).
    # Example genres value: "Adventure|Fantasy"
    def primary_genre(genres: str) -> str:
        if not isinstance(genres, str) or not genres:
            return "Unknown"
        return genres.split("|")[0].strip() or "Unknown"

    movies_df["genre_primary"] = movies_df["genres"].apply(primary_genre)

    # Optional rating limit.
    if args.max_ratings and args.max_ratings > 0:
        ratings_df = ratings_df.head(args.max_ratings)

    print("Seeding SQLite database...")
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Insert movies (movieId => Movies.id).
    movies_rows = [
        (int(row.movieId), str(row.title), str(row.genre_primary))
        for row in movies_df.itertuples(index=False)
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO Movies (id, title, genre)
        VALUES (?, ?, ?)
        """,
        movies_rows,
    )
    conn.commit()

    # Insert users and ratings.
    # Passwords for MovieLens seed users are a demo password (for dev only).
    seed_password_hash = generate_password_hash("demo-password")

    unique_user_ids = sorted(int(x) for x in ratings_df["userId"].unique().tolist())
    if args.max_users and args.max_users > 0:
        unique_user_ids = unique_user_ids[: args.max_users]

    user_rows = [(uid, f"ml_user_{uid}", seed_password_hash) for uid in unique_user_ids]
    conn.executemany(
        """
        INSERT OR IGNORE INTO Users (id, username, password)
        VALUES (?, ?, ?)
        """,
        user_rows,
    )
    conn.commit()

    rating_rows = []
    for row in ratings_df.itertuples(index=False):
        uid = int(row.userId)
        mid = int(row.movieId)
        rating_float = float(row.rating)
        rating_int = int(round(rating_float))
        rating_int = max(1, min(5, rating_int))
        rating_rows.append((uid, mid, rating_int))

    conn.executemany(
        """
        INSERT INTO Ratings (user_id, movie_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, movie_id) DO UPDATE SET
            rating = excluded.rating
        """,
        rating_rows,
    )
    conn.commit()
    conn.close()

    print("Done!")
    print(f"Database path: {Config.DATABASE_PATH}")


if __name__ == "__main__":
    main()

