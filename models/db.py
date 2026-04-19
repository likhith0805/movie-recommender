from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from backend.config import Config


def get_db_path() -> str:
    Path(Config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return Config.DATABASE_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_user(username: str, password_hash: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO Users (username, password) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, password FROM Users WHERE username = ?",
            (username,),
        ).fetchone()
        return row


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username FROM Users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row


def upsert_rating(user_id: int, movie_id: int, rating: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO Ratings (user_id, movie_id, rating)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, movie_id) DO UPDATE SET
                rating = excluded.rating
            """,
            (user_id, movie_id, rating),
        )
        conn.commit()


def get_user_rating(user_id: int, movie_id: int) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rating FROM Ratings WHERE user_id = ? AND movie_id = ?",
            (user_id, movie_id),
        ).fetchone()
        return int(row["rating"]) if row else None


def get_movie(movie_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, genre FROM Movies WHERE id = ?",
            (movie_id,),
        ).fetchone()
        return row


def search_movies(query: str | None = None, genre: str | None = None) -> list[sqlite3.Row]:
    query = (query or "").strip()
    genre = (genre or "").strip()

    where = []
    params: list[object] = []

    if query:
        where.append("title LIKE ?")
        params.append(f"%{query}%")

    if genre:
        where.append("genre LIKE ?")
        params.append(f"%{genre}%")

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    sql = f"""
        SELECT id, title, genre
        FROM Movies
        {where_sql}
        ORDER BY title ASC
        LIMIT 200
    """

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return list(rows)


def get_movies_with_ratings(user_id: Optional[int], query: str | None, genre: str | None, limit: int) -> list[dict]:
    query = (query or "").strip()
    genre = (genre or "").strip()

    where = []
    params: list[object] = []
    if query:
        where.append("m.title LIKE ?")
        params.append(f"%{query}%")
    if genre:
        where.append("m.genre LIKE ?")
        params.append(f"%{genre}%")

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    user_id_sql = "NULL" if user_id is None else "?"

    # Use subquery for avg rating to avoid join multiplication.
    sql = f"""
        SELECT
            m.id,
            m.title,
            m.genre,
            ra.avg_rating,
            ur.rating AS user_rating
        FROM Movies m
        {where_sql}
        LEFT JOIN (
            SELECT movie_id, AVG(rating) AS avg_rating
            FROM Ratings
            GROUP BY movie_id
        ) ra ON ra.movie_id = m.id
        LEFT JOIN Ratings ur
            ON ur.movie_id = m.id AND ur.user_id = {user_id_sql}
        ORDER BY m.title ASC
        LIMIT ?
    """

    if user_id is None:
        sql_params: list[object] = params + [limit]
    else:
        sql_params = params + [user_id, limit]

    with get_conn() as conn:
        rows = conn.execute(sql, sql_params).fetchall()

        results: list[dict] = []
        for r in rows:
            results.append(
                {
                    "id": int(r["id"]),
                    "title": r["title"],
                    "genre": r["genre"],
                    "avg_rating": None if r["avg_rating"] is None else float(r["avg_rating"]),
                    "user_rating": None if r["user_rating"] is None else int(r["user_rating"]),
                }
            )
        return results


def get_movie_with_ratings(user_id: Optional[int], movie_id: int) -> Optional[dict]:
    sql_user_id = "NULL" if user_id is None else "?"
    sql = f"""
        SELECT
            m.id,
            m.title,
            m.genre,
            ra.avg_rating,
            ur.rating AS user_rating
        FROM Movies m
        LEFT JOIN (
            SELECT movie_id, AVG(rating) AS avg_rating
            FROM Ratings
            GROUP BY movie_id
        ) ra ON ra.movie_id = m.id
        LEFT JOIN Ratings ur
            ON ur.movie_id = m.id AND ur.user_id = {sql_user_id}
        WHERE m.id = ?
    """

    params: list[object] = []
    if user_id is not None:
        params.append(user_id)
    params.append(movie_id)

    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        if not row:
            return None

        return {
            "id": int(row["id"]),
            "title": row["title"],
            "genre": row["genre"],
            "avg_rating": None if row["avg_rating"] is None else float(row["avg_rating"]),
            "user_rating": None if row["user_rating"] is None else int(row["user_rating"]),
        }


def get_ratings_dataframe() -> pd.DataFrame:
    """
    Returns a DataFrame with columns: user_id, movie_id, rating
    """

    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT user_id, movie_id, rating FROM Ratings",
            conn,
        )
    return df


def get_movies_dataframe() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT id, title, genre FROM Movies", conn)
    return df


def get_popular_movies(limit: int = 20) -> list[dict]:
    """
    Fallback list: highest average rating (with at least 1 rating).
    """

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                m.id,
                m.title,
                m.genre,
                AVG(r.rating) AS avg_rating,
                COUNT(r.rating) AS rating_count
            FROM Movies m
            JOIN Ratings r ON r.movie_id = m.id
            GROUP BY m.id
            ORDER BY rating_count DESC, avg_rating DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "id": int(r["id"]),
                    "title": r["title"],
                    "genre": r["genre"],
                    "avg_rating": float(r["avg_rating"]),
                    "rating_count": int(r["rating_count"]),
                }
            )
        return out


def get_users_by_ids(user_ids: Iterable[int]) -> dict[int, str]:
    user_ids = list(user_ids)
    if not user_ids:
        return {}

    placeholders = ",".join(["?"] * len(user_ids))
    sql = f"SELECT id, username FROM Users WHERE id IN ({placeholders})"

    with get_conn() as conn:
        rows = conn.execute(sql, user_ids).fetchall()
        return {int(r["id"]): r["username"] for r in rows}

