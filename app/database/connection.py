"""
Database connection manager using aiosqlite.

Implements a singleton pattern to ensure a single database connection
is shared across the application lifecycle.
"""

from pathlib import Path
from typing import Any, Optional

import aiosqlite

from app.config import settings


class Database:
    """Async SQLite database connection manager (singleton)."""

    _instance: Optional["Database"] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connection: Optional[aiosqlite.Connection] = None
        return cls._instance

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open a connection to the SQLite database.

        Ensures the parent directory exists before connecting so that
        the database file can be created automatically by SQLite.
        """
        if self._connection is not None:
            return

        db_path = Path(settings.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(str(db_path))
        self._connection.row_factory = aiosqlite.Row

        # Enable foreign-key enforcement (off by default in SQLite)
        await self._connection.execute("PRAGMA foreign_keys = ON;")

        # Enable WAL mode for better concurrent read performance
        await self._connection.execute("PRAGMA journal_mode = WAL;")

    async def disconnect(self) -> None:
        """Close the database connection if it is open."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    @property
    def is_connected(self) -> bool:
        """Return True if the database connection is currently open."""
        return self._connection is not None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> aiosqlite.Connection:
        """Raise an error if the database is not connected."""
        if self._connection is None:
            raise RuntimeError(
                "Database is not connected. Call `await db.connect()` first."
            )
        return self._connection

    @staticmethod
    def _row_to_dict(row: Optional[aiosqlite.Row]) -> Optional[dict[str, Any]]:
        """Convert an aiosqlite.Row to a plain dict, or return None."""
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _rows_to_dicts(rows: list[aiosqlite.Row]) -> list[dict[str, Any]]:
        """Convert a list of aiosqlite.Row objects to a list of dicts."""
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        query: str,
        params: Optional[tuple[Any, ...]] = None,
    ) -> aiosqlite.Cursor:
        """Execute a single SQL statement (INSERT / UPDATE / DELETE).

        Automatically commits the transaction after execution.
        Returns the cursor so callers can inspect ``lastrowid`` etc.
        """
        conn = self._ensure_connected()
        cursor = await conn.execute(query, params or ())
        await conn.commit()
        return cursor

    async def fetchone(
        self,
        query: str,
        params: Optional[tuple[Any, ...]] = None,
    ) -> Optional[dict[str, Any]]:
        """Execute a SELECT and return the first row as a dict, or None."""
        conn = self._ensure_connected()
        cursor = await conn.execute(query, params or ())
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def fetchall(
        self,
        query: str,
        params: Optional[tuple[Any, ...]] = None,
    ) -> list[dict[str, Any]]:
        """Execute a SELECT and return all rows as a list of dicts."""
        conn = self._ensure_connected()
        cursor = await conn.execute(query, params or ())
        rows = await cursor.fetchall()
        return self._rows_to_dicts(rows)

    async def execute_script(self, script: str) -> None:
        """Execute multiple SQL statements (e.g. a schema definition).

        Uses ``executescript`` which implicitly commits before running.
        """
        conn = self._ensure_connected()
        await conn.executescript(script)
        await conn.commit()


# Module-level singleton instance
db = Database()
