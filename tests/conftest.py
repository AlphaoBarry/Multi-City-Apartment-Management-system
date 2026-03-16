"""
Shared pytest fixtures for PAMS test suite.
Uses in-memory SQLite so tests never touch the real database.
"""

import os
import pytest

os.environ["PAMS_DB_PATH"] = ":memory:"

from database.connection import init_db, db


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset and re-initialise the database for every test."""
    db._connection = None  # reset singleton
    init_db()
    yield
    db.disconnect()
