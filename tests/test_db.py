"""Tests for DuckDB initialization and connection management."""

from pathlib import Path

import duckdb

from src.utils.db import get_connection, get_warehouse_path, init_warehouse


class TestGetWarehousePath:
    """Tests for warehouse path configuration."""

    def test_returns_path(self) -> None:
        """Warehouse path is a Path object."""
        path = get_warehouse_path()
        assert isinstance(path, Path)

    def test_path_is_duckdb_file(self) -> None:
        """Warehouse path ends with .duckdb extension."""
        path = get_warehouse_path()
        assert path.suffix == ".duckdb"


class TestGetConnection:
    """Tests for database connection management."""

    def test_connection_context_manager(self, tmp_path: Path) -> None:
        """Connection opens and closes cleanly."""
        db_path = tmp_path / "test.duckdb"
        with get_connection(db_path) as conn:
            result = conn.execute("SELECT 1 AS val").fetchone()
            assert result[0] == 1

    def test_connection_creates_file(self, tmp_path: Path) -> None:
        """DuckDB file is created on connection."""
        db_path = tmp_path / "new.duckdb"
        assert not db_path.exists()
        with get_connection(db_path) as conn:
            conn.execute("SELECT 1")
        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created if they don't exist."""
        db_path = tmp_path / "nested" / "dir" / "test.duckdb"
        with get_connection(db_path) as conn:
            conn.execute("SELECT 1")
        assert db_path.exists()


class TestInitWarehouse:
    """Tests for warehouse initialization."""

    def test_creates_schemas(self, tmp_path: Path) -> None:
        """All required schemas are created."""
        db_path = tmp_path / "warehouse.duckdb"
        init_warehouse(db_path)

        with duckdb.connect(str(db_path)) as conn:
            schemas = [
                row[0]
                for row in conn.execute(
                    "SELECT schema_name FROM information_schema.schemata"
                ).fetchall()
            ]

        for expected in ["raw", "staging", "intermediate", "marts"]:
            assert expected in schemas

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running init twice does not raise errors."""
        db_path = tmp_path / "warehouse.duckdb"
        init_warehouse(db_path)
        init_warehouse(db_path)
