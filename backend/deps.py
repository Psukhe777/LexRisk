"""
backend/deps.py — shared FastAPI dependencies.

TEMPORARY (Session 1): the caller is identified by an X-User-Id header.
JWT authentication lands in Session 3 and will replace current_user_id()
without touching the routers.
"""

from fastapi import Header


def current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """Identify the caller. Placeholder until JWT auth (Session 3)."""
    return (x_user_id or "").strip() or "anonymous"
