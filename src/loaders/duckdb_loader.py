"""DuckDB loader for writing extracted data into staging tables.

Handles creating staging tables, loading DataFrames into them,
and supporting both full refresh and append modes.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.utils.db import get_connection

logger = logging.getLogger(__name__)

_TYPE_MAP: dict[str, str] = {
    "INTEGER": "INTEGER",
    "DOUBLE": "DOUBLE",
    "VARCHAR": "VARCHAR",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "BOOLEAN",
}


class DuckDBLoader:
    """Load extracted data into DuckDB staging tables.

    Creates and manages staging tables in the DuckDB warehouse,
    supporting full refresh and incremental append operations.

    Args:
        db_path: Path to the DuckDB warehouse file.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def load_to_staging(
        self,
        df: pd.DataFrame,
        table_name: str,
        schema: list[dict[str, Any]],
        mode: str = "append",
    ) -> int:
        """Load a DataFrame into a DuckDB staging table.

        Args:
            df: DataFrame to load.
            table_name: Target table name (without schema prefix).
            schema: Column definitions from source config.
            mode: Load mode - 'append' or 'replace'.

        Returns:
            Number of rows loaded.

        Raises:
            ValueError: If mode is not 'append' or 'replace'.
        """
        if mode not in ("append", "replace"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'append' or 'replace'.")

        if df.empty:
            logger.warning("Empty DataFrame, skipping load for %s", table_name)
            return 0

        full_table = f"staging.{table_name}"

        with get_connection(self.db_path) as conn:
            conn.execute("CREATE SCHEMA IF NOT EXISTS staging")
            self._ensure_table(conn, full_table, schema)

            if mode == "replace":
                conn.execute(f"DELETE FROM {full_table}")
                logger.info("Cleared existing data from %s", full_table)

            df_with_meta = df.copy()
            df_with_meta["_loaded_at"] = datetime.now(timezone.utc).isoformat()

            conn.register("_df_to_load", df_with_meta)
            conn.execute(f"INSERT INTO {full_table} SELECT * FROM _df_to_load")
            conn.unregister("_df_to_load")

            row_count = conn.execute(f"SELECT count(*) FROM {full_table}").fetchone()[0]

        logger.info(
            "Loaded %d rows into %s (mode=%s, total=%d)",
            len(df),
            full_table,
            mode,
            row_count,
        )
        return len(df)

    def _ensure_table(
        self,
        conn: duckdb.DuckDBPyConnection,
        full_table: str,
        schema: list[dict[str, Any]],
    ) -> None:
        """Create the staging table if it doesn't exist.

        Args:
            conn: Active DuckDB connection.
            full_table: Fully qualified table name (schema.table).
            schema: Column definitions for the table.
        """
        columns = []
        for col in schema:
            col_type = _TYPE_MAP.get(col["type"].upper(), "VARCHAR")
            columns.append(f"{col['name']} {col_type}")

        columns.append("_loaded_at VARCHAR")

        columns_sql = ", ".join(columns)
        create_sql = f"CREATE TABLE IF NOT EXISTS {full_table} ({columns_sql})"
        conn.execute(create_sql)
        logger.debug("Ensured table exists: %s", full_table)

    def get_row_count(self, table_name: str) -> int:
        """Get the current row count of a staging table.

        Args:
            table_name: Table name (without schema prefix).

        Returns:
            Number of rows in the table.
        """
        full_table = f"staging.{table_name}"
        with get_connection(self.db_path) as conn:
            result = conn.execute(f"SELECT count(*) FROM {full_table}").fetchone()
            return result[0]

    def get_table_schema(self, table_name: str) -> list[dict[str, str]]:
        """Get the column schema of a staging table.

        Args:
            table_name: Table name (without schema prefix).

        Returns:
            List of column definitions with name and type.
        """
        with get_connection(self.db_path) as conn:
            columns = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'staging' AND table_name = ?",
                [table_name],
            ).fetchall()
            return [{"name": col[0], "type": col[1]} for col in columns]

    def table_exists(self, table_name: str) -> bool:
        """Check if a staging table exists.

        Args:
            table_name: Table name (without schema prefix).

        Returns:
            True if the table exists, False otherwise.
        """
        with get_connection(self.db_path) as conn:
            result = conn.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'staging' AND table_name = ?",
                [table_name],
            ).fetchone()
            return result[0] > 0
