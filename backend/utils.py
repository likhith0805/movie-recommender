from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from flask import jsonify, session


def current_user_id() -> Optional[int]:
    """
    Returns the currently logged-in user's id (or None).
    Uses Flask cookie-based sessions.
    """

    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


F = TypeVar("F", bound=Callable[..., Any])


def login_required_json(f: F) -> F:
    """
    Decorator for JSON APIs. Returns HTTP 401 when the user is not logged in.
    """

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any):
        if current_user_id() is None:
            return jsonify({"error": "login_required"}), 401
        return f(*args, **kwargs)

    return wrapper  # type: ignore[return-value]

