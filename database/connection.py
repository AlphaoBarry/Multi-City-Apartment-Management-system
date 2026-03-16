"""
PAMS - Paragon Apartment Management System
Database Connection Module

Handles SQLite connection setup, configuration, and lifecycle management.
Uses a singleton pattern so the entire app shares one connection pool.
"""

import sqlite3
import os
import logging
from pathlib import Path
from contextlib import contextmanager

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("PAMS_DB_PATH", str(BASE_DIR / "data" / "pams.db"))


class DatabaseConnection:
    """
    Singleton SQLite connection manager for PAMS.
    Ensures a single shared connection throughout the application lifecycle.
    """

    _instance = None
    _connection: sqlite3.Connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> sqlite3.Connection:
        """Open (or return existing) SQLite connection."""
        if self._connection is None:
            # Ensure /data directory exists
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

            self._connection = sqlite3.connect(
                DB_PATH,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,   # Required for PyQt multi-thread access
            )

            # ── Pragmas ───────────────────────────────────────────────────
            self._connection.execute("PRAGMA journal_mode=WAL;")   # Write-Ahead Logging for concurrency
            self._connection.execute("PRAGMA foreign_keys=ON;")    # Enforce FK constraints
            self._connection.execute("PRAGMA busy_timeout=5000;")  # 5s wait on locked DB (NFR-3)

            # Return rows as dict-like objects (access by column name)
            self._connection.row_factory = sqlite3.Row

            logger.info(f"✅ SQLite connected → {DB_PATH}")
        return self._connection

    def disconnect(self):
        """Close the SQLite connection cleanly."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("🔌 SQLite connection closed.")

    def get_connection(self) -> sqlite3.Connection:
        """Get the active connection, creating one if needed."""
        return self.connect()


# ── Module-level singleton ────────────────────────────────────────────────────
db = DatabaseConnection()


@contextmanager
def get_db():
    """
    Context manager for safe database transactions.

    Usage:
        with get_db() as conn:
            conn.execute("INSERT INTO ...")
            # auto-commits on success, auto-rollbacks on exception
    """
    conn = db.get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ DB transaction failed, rolled back: {e}")
        raise


def init_db():
    """
    Initialise the database — creates all tables if they don't exist.
    Call this once at application startup.
    """
    from database.schema import CREATE_TABLES_SQL
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        for statement in CREATE_TABLES_SQL:
            cursor.execute(statement)
        conn.commit()
        logger.info("✅ All PAMS tables initialised.")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Schema init failed: {e}")
        raise