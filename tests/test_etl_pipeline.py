"""Tests for ETL pipeline orchestration logic."""

import sqlite3
from pathlib import Path

import pytest

from src.pipelines.etl_pipeline import run_csv_pipeline, run_db_pipeline
from src.utils.db import init_warehouse


@pytest.fixture()
def warehouse(tmp_path: Path) -> Path:
    """Create a temporary DuckDB warehouse."""
    db_path = tmp_path / "warehouse.duckdb"
    init_warehouse(db_path)
    return db_path


@pytest.fixture()
def csv_source(tmp_path: Path) -> Path:
    """Create temp CSV order files."""
    csv_dir = tmp_path / "orders"
    csv_dir.mkdir()
    (csv_dir / "orders.csv").write_text(
        "order_id,customer_id,product_id,quantity,price,order_date,status\n"
        "1,10,101,2,29.99,2024-01-15 10:30:00,completed\n"
        "2,20,102,1,49.99,2024-02-01 11:00:00,completed\n"
    )
    return csv_dir


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    """Create temp SQLite customer database."""
    db_path = tmp_path / "source.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT, email TEXT,
            created_at TEXT, updated_at TEXT, tier TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Alice", "alice@test.com", "2024-01-01", "2024-01-01", "gold"),
            (2, "Bob", "bob@test.com", "2024-02-01", "2024-03-01", "silver"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


class TestCSVPipeline:
    """Tests for the CSV extraction pipeline."""

    def test_full_pipeline(
        self, warehouse: Path, csv_source: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """End-to-end CSV pipeline loads data."""
        source_config = {
            "sources": {
                "csv_orders": {
                    "type": "csv",
                    "path": str(csv_source),
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
            }
        }
        monkeypatch.setattr(
            "src.pipelines.etl_pipeline.load_source_config",
            lambda: source_config,
        )

        bm_file = str(tmp_path / "bookmarks.json")
        result = run_csv_pipeline(
            source_name="csv_orders",
            db_path=warehouse,
            bookmark_file=bm_file,
        )

        assert result["rows_extracted"] == 2
        assert result["rows_loaded"] == 2

    def test_empty_source(self, warehouse: Path, tmp_path: Path, monkeypatch) -> None:
        """Empty CSV directory returns zero rows."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        source_config = {
            "sources": {
                "csv_orders": {
                    "type": "csv",
                    "path": str(empty_dir),
                    "schema": [],
                    "incremental": False,
                }
            }
        }
        monkeypatch.setattr(
            "src.pipelines.etl_pipeline.load_source_config",
            lambda: source_config,
        )

        result = run_csv_pipeline(
            source_name="csv_orders",
            db_path=warehouse,
            bookmark_file=str(tmp_path / "bm.json"),
        )

        assert result["rows_extracted"] == 0
        assert result["rows_loaded"] == 0


class TestDBPipeline:
    """Tests for the database extraction pipeline."""

    def test_full_pipeline(
        self, warehouse: Path, source_db: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """End-to-end database pipeline loads data."""
        source_config = {
            "sources": {
                "db_customers": {
                    "type": "database",
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
            }
        }
        monkeypatch.setattr(
            "src.pipelines.etl_pipeline.load_source_config",
            lambda: source_config,
        )

        bm_file = str(tmp_path / "bookmarks.json")
        result = run_db_pipeline(
            source_name="db_customers",
            db_path=warehouse,
            bookmark_file=bm_file,
        )

        assert result["rows_extracted"] == 2
        assert result["rows_loaded"] == 2


class TestDAGDefinitions:
    """Tests for DAG module imports and configuration."""

    def test_csv_dag_config(self) -> None:
        """CSV DAG has correct configuration."""
        from dags.etl_csv import DAG_ID, DEFAULT_ARGS

        assert DAG_ID == "etl_csv_orders"
        assert DEFAULT_ARGS["retries"] == 2

    def test_api_dag_config(self) -> None:
        """API DAG has correct configuration."""
        from dags.etl_api import DAG_ID, DEFAULT_ARGS

        assert DAG_ID == "etl_api_transactions"
        assert DEFAULT_ARGS["retries"] == 3

    def test_db_dag_config(self) -> None:
        """Database DAG has correct configuration."""
        from dags.etl_database import DAG_ID, DEFAULT_ARGS

        assert DAG_ID == "etl_db_customers"
        assert DEFAULT_ARGS["retries"] == 2

    def test_master_dag_config(self) -> None:
        """Master DAG has correct configuration."""
        from dags.master_orchestration import DAG_ID, DEFAULT_ARGS

        assert DAG_ID == "master_orchestration"
        assert "sla" in DEFAULT_ARGS
