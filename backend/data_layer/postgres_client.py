"""PostgreSQL client for metadata and backup vector storage.

Introduced in Story 003 to encapsulate database connectivity and basic
schema verification for the RAG system.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


class PostgresClient:
    """Client for PostgreSQL database operations."""

    def __init__(self, connection_string: str | None = None) -> None:
        """Initialize PostgreSQL client.

        Parameters
        ----------
        connection_string:
            PostgreSQL connection URL. If not provided, uses the DATABASE_URL
            environment variable.
        """

        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise ValueError("DATABASE_URL not set")

        self.engine: Engine = create_engine(
            self.connection_string,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

        logger.info("PostgreSQL client initialized", extra={"url": self._redacted_url})

    @property
    def _redacted_url(self) -> str:
        """Return the connection string with password redacted for logging."""

        if "@" not in self.connection_string:
            return self.connection_string
        # naive redaction: split on '://user:pass@host' pattern
        try:
            prefix, rest = self.connection_string.split("://", 1)
            userinfo, hostpart = rest.split("@", 1)
            if ":" in userinfo:
                user, _ = userinfo.split(":", 1)
                userinfo_redacted = f"{user}:***"
            else:
                userinfo_redacted = userinfo
            return f"{prefix}://{userinfo_redacted}@{hostpart}"
        except Exception:  # pragma: no cover - best-effort only
            return self.connection_string

    def get_session(self) -> Session:
        """Get a new SQLAlchemy session."""

        return self.SessionLocal()

    def test_connection(self) -> bool:
        """Test database connectivity with a simple SELECT 1.

        Returns True on success, False on failure (and logs the error).
        """

        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection successful")
            return True
        except (
            Exception
        ) as exc:  # pragma: no cover - behavior logged, surfaced to tests
            logger.error("PostgreSQL connection failed", exc_info=exc)
            return False

    def verify_schema(self) -> Dict[str, List[str]]:
        """Verify core schema objects exist.

        Returns a dict with lists of extensions, tables, and indexes found.
        Intended for integration tests, not for hot-path runtime usage.
        """

        results: Dict[str, List[str]] = {
            "extensions": [],
            "tables": [],
            "indexes": [],
        }

        with self.engine.connect() as conn:
            ext_result = conn.execute(
                text(
                    """
                    SELECT extname
                    FROM pg_extension
                    WHERE extname IN ('uuid-ossp', 'vector', 'pg_trgm')
                    """
                )
            )
            results["extensions"] = [row[0] for row in ext_result]

            table_result = conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
            )
            results["tables"] = [row[0] for row in table_result]

            index_result = conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    """
                )
            )
            results["indexes"] = [row[0] for row in index_result]

        logger.info(
            "PostgreSQL schema verified",
            extra={
                "extensions": results["extensions"],
                "tables": results["tables"],
                "index_count": len(results["indexes"]),
            },
        )
        return results
