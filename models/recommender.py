from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from models import db


@dataclass
class RecommendationItem:
    movie_id: int
    title: str
    genre: str
    score: float
    avg_rating: Optional[float]
    why: str


class CollaborativeFilteringRecommender:
    """
    Beginner-friendly collaborative filtering recommender using:
    - user-item matrix (ratings)
    - cosine similarity between users
    - predicted scores for unseen movies via weighted averages
    """

    def __init__(self, min_ratings_for_personal: int = 2):
        self.min_ratings_for_personal = min_ratings_for_personal

        self._signature: Optional[tuple[int, float]] = None
        self._ratings_matrix: Optional[np.ndarray] = None  # (n_users, n_movies)
        self._user_ids: Optional[np.ndarray] = None  # (n_users,)
        self._movie_ids: Optional[np.ndarray] = None  # (n_movies,)
        self._similarity: Optional[np.ndarray] = None  # (n_users, n_users)
        self._movies_df: Optional[pd.DataFrame] = None  # id,title,genre
        self._movie_id_to_row: Optional[dict[int, int]] = None
        self._avg_rating_by_movie: Optional[np.ndarray] = None  # (n_movies,)

    def _compute_signature(self) -> tuple[int, float]:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c, COALESCE(SUM(rating), 0) AS s FROM Ratings"
            ).fetchone()
            assert row is not None
            return int(row["c"]), float(row["s"])

    def refresh_if_needed(self) -> None:
        signature = self._compute_signature()
        if self._signature == signature:
            return

        ratings_df = db.get_ratings_dataframe()
        movies_df = db.get_movies_dataframe()

        self._movies_df = movies_df
        self._movie_id_to_row = {int(mid): i for i, mid in enumerate(movies_df["id"].tolist())}

        if ratings_df.empty:
            self._signature = signature
            self._ratings_matrix = None
            self._user_ids = None
            self._movie_ids = None
            self._similarity = None
            self._avg_rating_by_movie = None
            return

        # Pivot: rows are users, columns are movies.
        user_item = ratings_df.pivot_table(
            index="user_id",
            columns="movie_id",
            values="rating",
            fill_value=0,
        )

        self._user_ids = user_item.index.to_numpy(dtype=int)
        self._movie_ids = user_item.columns.to_numpy(dtype=int)
        self._ratings_matrix = user_item.to_numpy(dtype=float)

        # Cosine similarity between users in rating-space.
        self._similarity = cosine_similarity(self._ratings_matrix)

        # Per-movie average rating (for cold-start / fallback).
        # Only consider non-zero ratings in the denominator.
        mask = self._ratings_matrix > 0
        sum_r = (self._ratings_matrix * mask).sum(axis=0)
        count_r = mask.sum(axis=0)
        avg = np.divide(sum_r, count_r, out=np.zeros_like(sum_r), where=count_r > 0)
        self._avg_rating_by_movie = avg

        self._signature = signature

    def _popular_fallback(self, genre: Optional[str], top_n: int) -> list[RecommendationItem]:
        popular = db.get_popular_movies(limit=200)
        if genre:
            genre_lower = genre.lower().strip()
            popular = [m for m in popular if genre_lower in (m["genre"] or "").lower()]

        top = popular[:top_n]
        if not top:
            return []

        # Provide a simple "why" explanation.
        out: list[RecommendationItem] = []
        for m in top:
            why = "Popular with many users (high average rating)."
            out.append(
                RecommendationItem(
                    movie_id=int(m["id"]),
                    title=m["title"],
                    genre=m["genre"],
                    score=float(m.get("avg_rating", 0.0)),
                    avg_rating=float(m.get("avg_rating", 0.0)) if m.get("avg_rating") is not None else None,
                    why=why,
                )
            )
        return out

    def recommend_popular(self, genre: Optional[str], top_n: int = 5) -> list[RecommendationItem]:
        """
        Public wrapper for the fallback list.
        Useful for chatbot responses and cold-start users.
        """

        return self._popular_fallback(genre=genre, top_n=top_n)

    def _get_movie_info(self, movie_id: int) -> tuple[str, str]:
        assert self._movies_df is not None
        # movies_df is small; use boolean match for clarity.
        row = self._movies_df[self._movies_df["id"] == movie_id]
        if len(row) == 0:
            return str(movie_id), "Unknown"
        r = row.iloc[0]
        return str(r["title"]), str(r["genre"])

    def _recommend_for_one_user(
        self,
        user_id: int,
        genre: Optional[str],
        top_n: int,
        top_k_sim_users: int = 10,
    ) -> list[RecommendationItem]:
        self.refresh_if_needed()

        if self._ratings_matrix is None or self._user_ids is None or self._movie_ids is None:
            return self._popular_fallback(genre, top_n)

        # Map the user_id to matrix row index.
        matches = np.where(self._user_ids == user_id)[0]
        if len(matches) == 0:
            return self._popular_fallback(genre, top_n)

        u_idx = int(matches[0])
        user_ratings_row = self._ratings_matrix[u_idx, :]
        rated_mask = user_ratings_row > 0
        if rated_mask.sum() < self.min_ratings_for_personal:
            return self._popular_fallback(genre, top_n)

        # Similarity vector for this user.
        sims = self._similarity[u_idx, :].astype(float)  # (n_users,)

        # We only want positive similarity contributions.
        # (With non-negative ratings, cosine similarity is usually >= 0 anyway.)
        positive_mask = sims > 0
        if not positive_mask.any():
            return self._popular_fallback(genre, top_n)

        # Weighted prediction:
        # score[m] = sum_v sim(u,v)*rating(v,m) / sum_v sim(u,v)*I(rating(v,m) > 0)
        mask_rated_other_per_movie = (self._ratings_matrix > 0).astype(float)  # (n_users, n_movies)

        numer = sims @ self._ratings_matrix  # (n_movies,)
        denom = sims @ mask_rated_other_per_movie  # (n_movies,)
        scores = np.divide(numer, denom, out=np.zeros_like(numer), where=denom > 0)

        # Exclude movies already rated by this user.
        scores[rated_mask] = -np.inf

        # Optionally filter candidates by genre after scoring.
        movie_genre_map: dict[int, str] = {}
        if genre:
            genre_lower = genre.lower().strip()
            # Build a quick map for movies matching the genre.
            for i, mid in enumerate(self._movie_ids.tolist()):
                title, mgenre = self._get_movie_info(mid)
                movie_genre_map[mid] = mgenre
            allowed = np.array(
                [genre_lower in (movie_genre_map.get(int(mid), "") or "").lower() for mid in self._movie_ids],
                dtype=bool,
            )
            # If a movie doesn't match genre, exclude it.
            scores[~allowed] = -np.inf

        top_indices = np.argsort(scores)[::-1][:top_n]

        # Prepare "why" explanations using top similar contributing users.
        top_sorted = [int(i) for i in top_indices if np.isfinite(scores[i])]
        if not top_sorted:
            return self._popular_fallback(genre, top_n)

        similar_user_ids = self._user_ids  # alias
        rating_matrix = self._ratings_matrix

        # Preload usernames for similar users.
        # We'll query only the users that might appear in explanations.
        # For each recommended movie, we look at the top contributing users.
        out: list[RecommendationItem] = []
        usernames = db.get_users_by_ids(similar_user_ids.tolist())

        for m_idx in top_sorted:
            movie_id = int(self._movie_ids[m_idx])
            title, movie_genre = self._get_movie_info(movie_id)
            score = float(scores[m_idx])

            # Contributing similar users for this movie.
            # Score contribution uses sim * rating(v,m).
            contrib_sims = sims.copy()
            rated_by_others_mask = rating_matrix[:, m_idx] > 0
            contrib_candidates = np.where(positive_mask & rated_by_others_mask)[0]

            if len(contrib_candidates) == 0:
                why = "Similar users rated this highly."
            else:
                # Rank contributors by similarity-weighted rating.
                contrib_rank = sorted(
                    contrib_candidates.tolist(),
                    key=lambda v: sims[v] * rating_matrix[v, m_idx],
                    reverse=True,
                )[:3]
                details = []
                for v in contrib_rank:
                    vid = int(similar_user_ids[v])
                    ur = int(rating_matrix[v, m_idx])
                    uname = usernames.get(vid, f"user {vid}")
                    details.append(f"{uname} ({ur}/5)")
                why = f"Similar users liked this: {', '.join(details)}."

            out.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=title,
                    genre=movie_genre,
                    score=score,
                    avg_rating=float(self._avg_rating_by_movie[m_idx]) if self._avg_rating_by_movie is not None else None,
                    why=why,
                )
            )

        return out[:top_n]

    def recommend_personal(
        self, user_id: int, genre: Optional[str], top_n: int = 5
    ) -> list[RecommendationItem]:
        return self._recommend_for_one_user(user_id=user_id, genre=genre, top_n=top_n)

    def recommend_group(
        self, user_ids: list[int], genre: Optional[str], top_n: int = 5
    ) -> list[RecommendationItem]:
        self.refresh_if_needed()

        # If we have no ratings data, fallback.
        if self._ratings_matrix is None or self._user_ids is None or self._movie_ids is None:
            return self._popular_fallback(genre, top_n)

        movie_count = self._movie_ids.shape[0]
        rating_matrix = self._ratings_matrix
        sims = self._similarity

        # Compute a per-member score vector for all movies.
        member_scores: list[np.ndarray] = []
        members_rated_masks: list[np.ndarray] = []

        user_id_to_index = {int(uid): i for i, uid in enumerate(self._user_ids.tolist())}
        usernames = db.get_users_by_ids(user_ids)

        for uid in user_ids:
            if uid not in user_id_to_index:
                # Cold-start member: use avg rating.
                member_scores.append(self._avg_rating_by_movie.copy())
                members_rated_masks.append(np.zeros(movie_count, dtype=bool))
                continue

            u_idx = user_id_to_index[uid]
            rated_mask = rating_matrix[u_idx, :] > 0
            if rated_mask.sum() < self.min_ratings_for_personal:
                member_scores.append(self._avg_rating_by_movie.copy())
                members_rated_masks.append(rated_mask)
                continue

            sims_u = sims[u_idx, :].astype(float)
            positive_mask = sims_u > 0
            mask_rated_other_per_movie = (rating_matrix > 0).astype(float)
            numer = sims_u @ rating_matrix
            denom = sims_u @ mask_rated_other_per_movie
            scores = np.divide(numer, denom, out=np.zeros_like(numer), where=denom > 0)
            # Exclude movies already rated by this member from their score to reduce bias.
            scores[rated_mask] = -np.inf
            member_scores.append(scores)
            members_rated_masks.append(rated_mask)

        combined = np.sum(np.stack(member_scores, axis=0), axis=0)  # (n_movies,)

        # "Common" recommendations: don't recommend movies any group member already rated.
        exclude_mask = np.zeros(movie_count, dtype=bool)
        for rm in members_rated_masks:
            exclude_mask = exclude_mask | rm
        combined[exclude_mask] = -np.inf

        # Optional genre filtering.
        if genre:
            genre_lower = genre.lower().strip()
            allowed = np.array(
                [
                    genre_lower in (str(self._get_movie_info(int(mid))[1]) or "").lower()
                    for mid in self._movie_ids.tolist()
                ],
                dtype=bool,
            )
            combined[~allowed] = -np.inf

        top_indices = np.argsort(combined)[::-1][:top_n]
        top_sorted = [int(i) for i in top_indices if np.isfinite(combined[i])]
        if not top_sorted:
            return self._popular_fallback(genre, top_n)

        out: list[RecommendationItem] = []
        for m_idx in top_sorted:
            movie_id = int(self._movie_ids[m_idx])
            title, movie_genre = self._get_movie_info(movie_id)
            score = float(combined[m_idx])

            # Pick best member for this movie and re-use their "why" logic in a simplified way.
            best_member_idx = int(np.argmax([s[m_idx] for s in member_scores]))
            best_member_id = user_ids[best_member_idx]
            best_member_name = usernames.get(best_member_id, f"user {best_member_id}")

            # Find top similar contributors for that best member.
            # If member is cold-start (no similarity row), explain with avg rating.
            if best_member_id not in user_id_to_index:
                why = f"All of you seem likely to enjoy this (based on average ratings)."
            else:
                u_idx = user_id_to_index[best_member_id]
                sims_u = sims[u_idx, :].astype(float)
                rated_by_other_mask = rating_matrix[:, m_idx] > 0
                candidates = np.where((sims_u > 0) & rated_by_other_mask)[0]
                if len(candidates) == 0:
                    why = f"Recommended for your group's combined taste (top combined score)."
                else:
                    contrib_rank = sorted(
                        candidates.tolist(),
                        key=lambda v: sims_u[v] * rating_matrix[v, m_idx],
                        reverse=True,
                    )[:3]
                    uname_map = db.get_users_by_ids(
                        [int(self._user_ids[v]) for v in contrib_rank]
                    )
                    details = []
                    for v in contrib_rank:
                        vid = int(self._user_ids[v])
                        ur = int(rating_matrix[v, m_idx])
                        uname = uname_map.get(vid, f"user {vid}")
                        details.append(f"{uname} ({ur}/5)")
                    why = (
                        f"{best_member_name} has similar tastes to users who rated this highly: "
                        f"{', '.join(details)}."
                    )

            out.append(
                RecommendationItem(
                    movie_id=movie_id,
                    title=title,
                    genre=movie_genre,
                    score=score,
                    avg_rating=float(self._avg_rating_by_movie[m_idx]) if self._avg_rating_by_movie is not None else None,
                    why=why,
                )
            )

        return out[:top_n]

