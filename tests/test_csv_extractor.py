"""Tests for the CSV extractor module."""

from pathlib import Path

import pandas as pd
import pytest

from src.extractors.csv_extractor import CSVExtractor


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """Create a temporary CSV file with sample order data."""
    csv_dir = tmp_path / "orders"
    csv_dir.mkdir()
    csv_file = csv_dir / "orders.csv"
    csv_file.write_text(
        "order_id,customer_id,product_id,quantity,price,order_date,status\n"
        "1,10,101,2,29.99,2024-01-15 10:30:00,completed\n"
        "2,20,102,1,49.99,2024-02-01 11:00:00,completed\n"
        "3,10,103,3,9.99,2024-03-01 09:15:00,pending\n"
    )
    return csv_dir


@pytest.fixture()
def source_config(sample_csv: Path) -> dict:
    """Build a source config pointing at the temp CSV directory."""
    return {
        "path": str(sample_csv),
        "file_pattern": "*.csv",
        "schema": [
            {"name": "order_id", "type": "INTEGER", "nullable": False},
            {"name": "customer_id", "type": "INTEGER", "nullable": False},
            {"name": "product_id", "type": "INTEGER", "nullable": False},
            {"name": "quantity", "type": "INTEGER", "nullable": False},
            {"name": "price", "type": "DOUBLE", "nullable": False},
            {"name": "order_date", "type": "TIMESTAMP", "nullable": False},
            {"name": "status", "type": "VARCHAR", "nullable": False},
        ],
        "incremental": True,
        "bookmark_column": "order_date",
    }


class TestCSVExtractorExtract:
    """Tests for the extract method."""

    def test_extracts_all_rows(self, source_config: dict) -> None:
        """Full extraction returns all rows."""
        extractor = CSVExtractor(source_config)
        df = extractor.extract()
        assert len(df) == 3

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        """Empty DataFrame when directory has no CSVs."""
        config = {"path": str(tmp_path / "empty"), "schema": []}
        (tmp_path / "empty").mkdir()
        extractor = CSVExtractor(config)
        df = extractor.extract()
        assert df.empty

    def test_incremental_filters_by_bookmark(self, source_config: dict) -> None:
        """Incremental mode filters rows after bookmark."""
        extractor = CSVExtractor(source_config)
        df = extractor.extract(last_bookmark="2024-01-20 00:00:00")
        assert len(df) == 2
        assert all(
            pd.to_datetime(df["order_date"]) > pd.to_datetime("2024-01-20 00:00:00")
        )

    def test_full_extract_ignores_bookmark_when_not_incremental(
        self, source_config: dict
    ) -> None:
        """Non-incremental config ignores bookmark parameter."""
        source_config["incremental"] = False
        extractor = CSVExtractor(source_config)
        df = extractor.extract(last_bookmark="2024-01-20 00:00:00")
        assert len(df) == 3

    def test_multiple_csv_files(self, tmp_path: Path) -> None:
        """Multiple CSVs in directory are concatenated."""
        csv_dir = tmp_path / "multi"
        csv_dir.mkdir()
        for i in range(3):
            f = csv_dir / f"data_{i}.csv"
            f.write_text("id,value\n" + f"{i},test_{i}\n")

        config = {"path": str(csv_dir), "schema": []}
        extractor = CSVExtractor(config)
        df = extractor.extract()
        assert len(df) == 3


class TestCSVExtractorValidateSchema:
    """Tests for schema validation."""

    def test_valid_schema_passes(self, source_config: dict) -> None:
        """Correct data passes validation."""
        extractor = CSVExtractor(source_config)
        df = extractor.extract()
        is_valid, errors = extractor.validate_schema(df)
        assert is_valid
        assert errors == []

    def test_missing_column_detected(self, source_config: dict) -> None:
        """Missing column produces validation error."""
        extractor = CSVExtractor(source_config)
        df = pd.DataFrame({"order_id": [1], "customer_id": [10]})
        is_valid, errors = extractor.validate_schema(df)
        assert not is_valid
        assert any("Missing columns" in e for e in errors)

    def test_null_in_nonnullable_detected(self, source_config: dict) -> None:
        """Null values in non-nullable column are flagged."""
        extractor = CSVExtractor(source_config)
        df = extractor.extract()
        df.loc[0, "order_id"] = None
        is_valid, errors = extractor.validate_schema(df)
        assert not is_valid
        assert any("null" in e.lower() for e in errors)

    def test_empty_dataframe_is_valid(self, source_config: dict) -> None:
        """Empty DataFrame passes validation."""
        extractor = CSVExtractor(source_config)
        df = pd.DataFrame()
        is_valid, errors = extractor.validate_schema(df)
        assert is_valid


class TestCSVExtractorBookmark:
    """Tests for bookmark tracking."""

    def test_get_bookmark_returns_max(self, source_config: dict) -> None:
        """Bookmark returns the max value of the bookmark column."""
        extractor = CSVExtractor(source_config)
        df = extractor.extract()
        bookmark = extractor.get_new_bookmark(df)
        assert bookmark is not None
        assert "2024-03-01" in bookmark

    def test_get_bookmark_empty_df(self, source_config: dict) -> None:
        """Empty DataFrame returns None bookmark."""
        extractor = CSVExtractor(source_config)
        bookmark = extractor.get_new_bookmark(pd.DataFrame())
        assert bookmark is None

    def test_get_bookmark_no_column(self, tmp_path: Path) -> None:
        """Returns None when bookmark column not configured."""
        config = {"path": str(tmp_path), "schema": []}
        extractor = CSVExtractor(config)
        df = pd.DataFrame({"a": [1, 2, 3]})
        bookmark = extractor.get_new_bookmark(df)
        assert bookmark is None
