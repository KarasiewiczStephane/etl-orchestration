"""Tests for the DuckDB loader module."""

from pathlib import Path

import pandas as pd
import pytest

from src.loaders.duckdb_loader import DuckDBLoader
from src.utils.db import init_warehouse


@pytest.fixture()
def warehouse(tmp_path: Path) -> Path:
    """Create a temporary DuckDB warehouse."""
    db_path = tmp_path / "test.duckdb"
    init_warehouse(db_path)
    return db_path


@pytest.fixture()
def loader(warehouse: Path) -> DuckDBLoader:
    """Create a loader instance with temp warehouse."""
    return DuckDBLoader(db_path=warehouse)


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Sample order data for loading."""
    return pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "customer_id": [10, 20, 30],
            "amount": [29.99, 49.99, 9.99],
            "order_date": ["2024-01-15", "2024-02-01", "2024-03-01"],
        }
    )


@pytest.fixture()
def schema() -> list[dict]:
    """Schema definition for sample data."""
    return [
        {"name": "order_id", "type": "INTEGER"},
        {"name": "customer_id", "type": "INTEGER"},
        {"name": "amount", "type": "DOUBLE"},
        {"name": "order_date", "type": "VARCHAR"},
    ]


class TestDuckDBLoaderLoadToStaging:
    """Tests for the load_to_staging method."""

    def test_append_mode(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Append mode adds rows to existing data."""
        loader.load_to_staging(sample_df, "orders", schema, mode="append")
        loader.load_to_staging(sample_df, "orders", schema, mode="append")
        assert loader.get_row_count("orders") == 6

    def test_replace_mode(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Replace mode clears and reloads data."""
        loader.load_to_staging(sample_df, "orders", schema, mode="append")
        loader.load_to_staging(sample_df, "orders", schema, mode="replace")
        assert loader.get_row_count("orders") == 3

    def test_returns_row_count(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Returns number of rows loaded."""
        count = loader.load_to_staging(sample_df, "orders", schema)
        assert count == 3

    def test_empty_df_returns_zero(self, loader: DuckDBLoader, schema: list) -> None:
        """Empty DataFrame returns 0 and skips load."""
        count = loader.load_to_staging(pd.DataFrame(), "orders", schema)
        assert count == 0

    def test_invalid_mode_raises(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            loader.load_to_staging(sample_df, "orders", schema, mode="upsert")

    def test_adds_loaded_at_column(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Loaded data includes _loaded_at metadata column."""
        loader.load_to_staging(sample_df, "orders", schema)
        table_schema = loader.get_table_schema("orders")
        col_names = [c["name"] for c in table_schema]
        assert "_loaded_at" in col_names

    def test_creates_table_if_not_exists(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Staging table is created automatically."""
        assert not loader.table_exists("new_table")
        loader.load_to_staging(sample_df, "new_table", schema)
        assert loader.table_exists("new_table")


class TestDuckDBLoaderTableOperations:
    """Tests for table inspection methods."""

    def test_get_row_count(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Row count matches loaded data."""
        loader.load_to_staging(sample_df, "orders", schema)
        assert loader.get_row_count("orders") == 3

    def test_get_table_schema(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Table schema has expected columns."""
        loader.load_to_staging(sample_df, "orders", schema)
        table_schema = loader.get_table_schema("orders")
        col_names = {c["name"] for c in table_schema}
        assert "order_id" in col_names
        assert "customer_id" in col_names

    def test_table_exists_false(self, loader: DuckDBLoader) -> None:
        """table_exists returns False for nonexistent table."""
        assert not loader.table_exists("nonexistent")

    def test_table_exists_true(
        self, loader: DuckDBLoader, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """table_exists returns True after loading."""
        loader.load_to_staging(sample_df, "orders", schema)
        assert loader.table_exists("orders")
