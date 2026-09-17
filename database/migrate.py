"""
SAT-SA Database Migration Runner.

Reads SQL files from ``database/migrations/`` in lexicographic order and applies
them against the configured SQLAlchemy engine.  Each migration is tracked in a
``_schema_migrations`` bookkeeping table so it is applied exactly once.

Both SQLite and PostgreSQL are supported.  PostgreSQL-only preamble lines
(e.g. ``CREATE EXTENSION``) are skipped when the target engine is SQLite.

Usage from application startup::

    from database.migrate import run_migrations
    run_migrations(engine)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("satsa.migrate")

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Patterns that must be stripped when running against SQLite.
_PG_ONLY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*CREATE\s+EXTENSION\b.*$", re.IGNORECASE),
    re.compile(r"^\s*ALTER\s+TABLE\s+\w+\s+ADD\s+CONSTRAINT\b.*$", re.IGNORECASE),
]


def _is_pg_only_line(line: str) -> bool:
    """Return True if *line* is a PostgreSQL-only statement that SQLite cannot execute."""
    stripped = line.strip().rstrip(";").strip()
    if not stripped:
        return False
    for pat in _PG_ONLY_PATTERNS:
        if pat.match(stripped):
            return True
    return False


def _ensure_bookkeeping_table(engine: Engine) -> None:
    """Create the ``_schema_migrations`` tracking table if it does not exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS _schema_migrations (
        filename   VARCHAR(256) PRIMARY KEY,
        applied_at TIMESTAMP NOT NULL
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _applied_migrations(engine: Engine) -> set[str]:
    """Return set of migration filenames already applied."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT filename FROM _schema_migrations")).fetchall()
    return {row[0] for row in rows}


def _discover_migrations() -> list[Path]:
    """Return migration SQL files sorted lexicographically."""
    if not _MIGRATIONS_DIR.is_dir():
        logger.warning("Migration directory does not exist: %s", _MIGRATIONS_DIR)
        return []
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    return files


def _adapt_sql_for_sqlite(sql: str) -> str:
    """Strip PostgreSQL-only statements from the migration SQL for SQLite compatibility."""
    out_lines: list[str] = []
    for line in sql.splitlines():
        if _is_pg_only_line(line):
            logger.debug("Skipping PG-only line: %s", line.strip())
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements, honouring semicolons.

    Simple splitter: split on ``';'`` at the end of a line (ignoring trailing
    whitespace) or as a standalone character.  This is sufficient for the DDL
    migrations used by SAT-SA.
    """
    statements: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        # Skip blank lines and pure comments
        if not stripped or stripped.startswith("--"):
            continue
        # Skip transaction markers — we run each migration inside engine.begin()
        if stripped.upper() in ("BEGIN;", "COMMIT;", "BEGIN", "COMMIT"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
    # Any trailing partial statement
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


def run_migrations(engine: Engine) -> Sequence[str]:
    """Apply pending migrations and return the list of newly applied filenames.

    Parameters
    ----------
    engine:
        A SQLAlchemy engine connected to the target database (SQLite or PostgreSQL).

    Returns
    -------
    list[str]
        Filenames of migrations that were applied during this call.
    """
    is_sqlite = "sqlite" in str(engine.url).lower()
    _ensure_bookkeeping_table(engine)
    already_applied = _applied_migrations(engine)

    migration_files = _discover_migrations()
    newly_applied: list[str] = []

    for mig_path in migration_files:
        fname = mig_path.name
        if fname in already_applied:
            logger.debug("Migration already applied, skipping: %s", fname)
            continue

        logger.info("Applying migration: %s", fname)
        raw_sql = mig_path.read_text(encoding="utf-8")

        if is_sqlite:
            raw_sql = _adapt_sql_for_sqlite(raw_sql)

        statements = _split_statements(raw_sql)
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
            # Record successful application
            conn.execute(
                text(
                    "INSERT INTO _schema_migrations (filename, applied_at) "
                    "VALUES (:fname, CURRENT_TIMESTAMP)"
                ),
                {"fname": fname},
            )

        newly_applied.append(fname)
        logger.info("Successfully applied migration: %s", fname)

    if not newly_applied:
        logger.info("Database schema is up to date (no pending migrations).")

    return newly_applied
