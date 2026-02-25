"""Database extractor with incremental loading support.

Connects to source databases (SQLite) and extracts data with
optional incremental loading via bookmark-based timestamp filtering.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DatabaseExtractor:
    """Extract data from a SQLite source database.

    Supports full and incremental extraction modes with schema
    validation against expected column definitions.

    Args:
        source_config: Source definition from sources.yaml containing
            connection_string, table, schema, and incremental settings.
    """

    def __init__(self, source_config: dict[str, Any]) -> None:
        self.connection_string = source_config["connection_string"]
        self.table = source_config["table"]
        self.schema = source_config.get("schema", [])
        self.incremental = source_config.get("incremental", False)
        self.bookmark_column = source_config.get("bookmark_column")

    @property
    def db_path(self) -> str:
        """Extract the file path from the SQLite connection string."""
        return self.connection_string.replace("sqlite:///", "")

    def extract(self, last_bookmark: Optional[str] = None) -> pd.DataFrame:
        """Extract data from the source database table.

        Reads the full table or applies incremental filtering based
        on the bookmark column and last known value.

        Args:
            last_bookmark: Previous bookmark value for incremental filtering.

        Returns:
            DataFrame containing extracted records.

        Raises:
            FileNotFoundError: If the database file does not exist.
        """
        db_file = Path(self.db_path)
        if not db_file.exists():
            raise FileNotFoundError(f"Database file not found: {db_file}")

        conn = sqlite3.connect(self.db_path)
        try:
            if self.incremental and last_bookmark and self.bookmark_column:
                query = (
                    f"SELECT * FROM {self.table} "  # noqa: S608
                    f"WHERE {self.bookmark_column} > ?"
                )
                df = pd.read_sql_query(query, conn, params=[last_bookmark])
                logger.info(
                    "Incremental extract from %s: %d rows after %s",
                    self.table,
                    len(df),
                    last_bookmark,
                )
            else:
                query = f"SELECT * FROM {self.table}"  # noqa: S608
                df = pd.read_sql_query(query, conn)
                logger.info("Full extract from %s: %d rows", self.table, len(df))

            return df
        finally:
            conn.close()

    def validate_schema(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Validate extracted data against the expected schema.

        Args:
            df: DataFrame to validate.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: list[str] = []

        if df.empty:
            return True, errors

        expected_columns = {col["name"] for col in self.schema}
        actual_columns = set(df.columns)

        missing = expected_columns - actual_columns
        if missing:
            errors.append(f"Missing columns: {sorted(missing)}")

        for col_def in self.schema:
            col_name = col_def["name"]
            if col_name not in df.columns:
                continue

            if not col_def.get("nullable", True):
                null_count = df[col_name].isna().sum()
                if null_count > 0:
                    errors.append(
                        f"Column '{col_name}' has {null_count} null values "
                        f"but is non-nullable"
                    )

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("Database schema validation passed for %s", self.table)
        else:
            logger.warning(
                "Database schema validation failed for %s: %d errors",
                self.table,
                len(errors),
            )

        return is_valid, errors

    def get_new_bookmark(self, df: pd.DataFrame) -> Optional[str]:
        """Get the latest bookmark value from extracted data.

        Args:
            df: Extracted DataFrame.

        Returns:
            String representation of the max bookmark column value,
            or None if not applicable.
        """
        if df.empty:
            return None
        if self.bookmark_column and self.bookmark_column in df.columns:
            return str(df[self.bookmark_column].max())
        return None
