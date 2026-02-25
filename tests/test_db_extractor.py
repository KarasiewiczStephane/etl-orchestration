"""Tests for the database extractor module."""

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.extractors.db_extractor import DatabaseExtractor


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with customer data."""
    db_path = tmp_path / "source.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tier TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Alice", "alice@test.com", "2024-01-01", "2024-01-01", "gold"),
            (2, "Bob", "bob@test.com", "2024-01-15", "2024-02-01", "silver"),
            (3, "Carol", "carol@test.com", "2024-02-01", "2024-03-01", None),
            (4, "Dave", "dave@test.com", "2024-03-01", "2024-04-01", "bronze"),
            (5, "Eve", "eve@test.com", "2024-04-01", "2024-05-01", "gold"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def db_config(source_db: Path) -> dict[str, Any]:
    """Build a database source config pointing at the temp SQLite DB."""
    return {
        "connection_string": f"sqlite:///{source_db}",
        "table": "customers",
        "schema": [
            {"name": "customer_id", "type": "INTEGER", "nullable": False},
            {"name": "name", "type": "VARCHAR", "nullable": False},
            {"name": "email", "type": "VARCHAR", "nullable": False},
            {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
            {"name": "updated_at", "type": "TIMESTAMP", "nullable": False},
            {"name": "tier", "type": "VARCHAR", "nullable": True},
        ],
        "incremental": True,
        "bookmark_column": "updated_at",
    }


class TestDatabaseExtractorExtract:
    """Tests for the extract method."""

    def test_full_extraction(self, db_config: dict) -> None:
        """Full extraction returns all rows."""
        extractor = DatabaseExtractor(db_config)
        df = extractor.extract()
        assert len(df) == 5

    def test_incremental_extraction(self, db_config: dict) -> None:
        """Incremental extraction filters by bookmark."""
        extractor = DatabaseExtractor(db_config)
        df = extractor.extract(last_bookmark="2024-02-15")
        assert len(df) == 3
        assert all(df["updated_at"] > "2024-02-15")

    def test_full_extract_when_no_bookmark(self, db_config: dict) -> None:
        """Full extract when bookmark is None."""
        extractor = DatabaseExtractor(db_config)
        df = extractor.extract(last_bookmark=None)
        assert len(df) == 5

    def test_non_incremental_ignores_bookmark(self, db_config: dict) -> None:
        """Non-incremental config ignores bookmark parameter."""
        db_config["incremental"] = False
        extractor = DatabaseExtractor(db_config)
        df = extractor.extract(last_bookmark="2024-04-01")
        assert len(df) == 5

    def test_raises_on_missing_db(self, tmp_path: Path) -> None:
        """FileNotFoundError for missing database file."""
        config = {
            "connection_string": f"sqlite:///{tmp_path / 'missing.db'}",
            "table": "test",
            "schema": [],
        }
        extractor = DatabaseExtractor(config)
        with pytest.raises(FileNotFoundError, match="Database file not found"):
            extractor.extract()


class TestDatabaseExtractorValidateSchema:
    """Tests for schema validation."""

    def test_valid_data_passes(self, db_config: dict) -> None:
        """Valid data passes schema validation."""
        extractor = DatabaseExtractor(db_config)
        df = extractor.extract()
        is_valid, errors = extractor.validate_schema(df)
        assert is_valid
        assert errors == []

    def test_missing_column_detected(self, db_config: dict) -> None:
        """Missing columns are detected."""
        extractor = DatabaseExtractor(db_config)
        df = pd.DataFrame({"customer_id": [1]})
        is_valid, errors = extractor.validate_schema(df)
        assert not is_valid
        assert any("Missing columns" in e for e in errors)

    def test_empty_dataframe_is_valid(self, db_config: dict) -> None:
        """Empty DataFrame passes validation."""
        extractor = DatabaseExtractor(db_config)
        is_valid, errors = extractor.validate_schema(pd.DataFrame())
        assert is_valid


class TestDatabaseExtractorBookmark:
    """Tests for bookmark tracking."""

    def test_get_bookmark_returns_max(self, db_config: dict) -> None:
        """Bookmark returns max value of bookmark column."""
        extractor = DatabaseExtractor(db_config)
        df = extractor.extract()
        bookmark = extractor.get_new_bookmark(df)
        assert bookmark == "2024-05-01"

    def test_get_bookmark_empty_df(self, db_config: dict) -> None:
        """Empty DataFrame returns None."""
        extractor = DatabaseExtractor(db_config)
        assert extractor.get_new_bookmark(pd.DataFrame()) is None

    def test_db_path_property(self, db_config: dict) -> None:
        """db_path property strips sqlite:/// prefix."""
        extractor = DatabaseExtractor(db_config)
        assert not extractor.db_path.startswith("sqlite:///")
