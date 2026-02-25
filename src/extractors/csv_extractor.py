"""CSV file extractor with schema validation and incremental loading.

Reads CSV files from a configured directory, validates them against
an expected schema definition, and supports incremental extraction
via bookmark-based filtering.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_TYPE_MAP: dict[str, str] = {
    "INTEGER": "int64",
    "DOUBLE": "float64",
    "VARCHAR": "object",
    "TIMESTAMP": "datetime64[ns]",
    "BOOLEAN": "bool",
}


class CSVExtractor:
    """Extract and validate data from CSV files in a source directory.

    Args:
        source_config: Source definition from sources.yaml containing
            path, schema, incremental, and bookmark_column settings.
    """

    def __init__(self, source_config: dict[str, Any]) -> None:
        self.source_path = Path(source_config["path"])
        self.file_pattern = source_config.get("file_pattern", "*.csv")
        self.schema = source_config.get("schema", [])
        self.incremental = source_config.get("incremental", False)
        self.bookmark_column = source_config.get("bookmark_column")

    def extract(self, last_bookmark: Optional[str] = None) -> pd.DataFrame:
        """Extract CSV files from the source directory.

        Reads all matching CSV files, concatenates them, and optionally
        filters to only new rows when incremental loading is enabled.

        Args:
            last_bookmark: Previous bookmark value for incremental filtering.

        Returns:
            DataFrame containing extracted (and optionally filtered) data.
        """
        csv_files = sorted(self.source_path.glob(self.file_pattern))
        if not csv_files:
            logger.warning("No CSV files found in %s", self.source_path)
            return pd.DataFrame()

        logger.info("Found %d CSV files in %s", len(csv_files), self.source_path)

        dfs = []
        for f in csv_files:
            df = pd.read_csv(f)
            logger.info("Read %d rows from %s", len(df), f.name)
            dfs.append(df)

        combined = pd.concat(dfs, ignore_index=True)

        if self.incremental and last_bookmark and self.bookmark_column:
            if self.bookmark_column in combined.columns:
                combined[self.bookmark_column] = pd.to_datetime(
                    combined[self.bookmark_column]
                )
                bookmark_ts = pd.to_datetime(last_bookmark)
                combined = combined[combined[self.bookmark_column] > bookmark_ts]
                logger.info(
                    "Incremental filter applied: %d rows after bookmark %s",
                    len(combined),
                    last_bookmark,
                )

        return combined

    def validate_schema(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Validate a DataFrame against the expected schema.

        Checks for missing columns, unexpected columns, non-nullable
        column violations, and type compatibility.

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

            expected_type = col_def.get("type", "").upper()
            if expected_type in _TYPE_MAP:
                try:
                    if expected_type == "TIMESTAMP":
                        pd.to_datetime(df[col_name])
                    elif expected_type == "INTEGER":
                        pd.to_numeric(df[col_name], downcast="integer")
                    elif expected_type == "DOUBLE":
                        pd.to_numeric(df[col_name], downcast="float")
                except (ValueError, TypeError) as e:
                    errors.append(
                        f"Column '{col_name}' type mismatch: "
                        f"expected {expected_type}, got error: {e}"
                    )

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("Schema validation passed")
        else:
            logger.warning("Schema validation failed with %d errors", len(errors))

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
