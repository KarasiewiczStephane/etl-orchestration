"""DuckDB database initialization and connection management.

Handles creating the warehouse database, schemas, and provides
connection context managers for safe resource management.
"""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import duckdb

from src.utils.config import load_config

logger = logging.getLogger(__name__)


def get_warehouse_path() -> Path:
    """Return the configured DuckDB warehouse file path.

    Returns:
        Path to the warehouse database file.
    """
    config = load_config()
    return Path(config["warehouse"]["path"])


@contextmanager
def get_connection(
    db_path: str | Path | None = None,
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager for DuckDB connections.

    Args:
        db_path: Optional override path for the database file.
            Uses configured warehouse path if None.

    Yields:
        Active DuckDB connection.
    """
    if db_path is None:
        db_path = get_warehouse_path()

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        yield conn
    finally:
        conn.close()


def init_warehouse(db_path: str | Path | None = None) -> None:
    """Initialize the DuckDB warehouse with required schemas.

    Creates the raw, staging, intermediate, and marts schemas
    if they don't already exist.

    Args:
        db_path: Optional override path for the database file.
    """
    schemas = ["raw", "staging", "intermediate", "marts"]

    with get_connection(db_path) as conn:
        for schema in schemas:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            logger.info("Ensured schema exists: %s", schema)

    logger.info("Warehouse initialized successfully")
