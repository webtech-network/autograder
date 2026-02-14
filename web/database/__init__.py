"""Database module for the autograder web API."""

from web.database.base import Base
from web.database.session import get_session, init_db

__all__ = ["Base", "get_session", "init_db"]
