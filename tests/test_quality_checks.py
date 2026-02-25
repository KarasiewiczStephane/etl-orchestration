"""Tests for data quality checks module."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.quality.checks import QualityChecker, QualityCheckResult


@pytest.fixture()
def checker() -> QualityChecker:
    """Create a QualityChecker instance."""
    return QualityChecker()


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Sample DataFrame for quality checks."""
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
    """Expected schema definition."""
    return [
        {"name": "order_id", "type": "INTEGER", "nullable": False},
        {"name": "customer_id", "type": "INTEGER", "nullable": False},
        {"name": "amount", "type": "DOUBLE", "nullable": False},
        {"name": "order_date", "type": "VARCHAR", "nullable": False},
    ]


class TestQualityCheckResult:
    """Tests for QualityCheckResult."""

    def test_to_dict(self) -> None:
        """Result converts to dictionary correctly."""
        result = QualityCheckResult("test", passed=True, details="ok")
        d = result.to_dict()
        assert d["check_name"] == "test"
        assert d["passed"] is True
        assert d["details"] == "ok"
        assert "timestamp" in d

    def test_default_severity(self) -> None:
        """Default severity is warning."""
        result = QualityCheckResult("test", passed=True)
        assert result.severity == "warning"


class TestSchemaCheck:
    """Tests for schema validation check."""

    def test_valid_schema(
        self, checker: QualityChecker, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Valid DataFrame passes schema check."""
        result = checker.check_schema(sample_df, schema)
        assert result.passed

    def test_missing_columns(self, checker: QualityChecker) -> None:
        """Missing columns fail schema check."""
        df = pd.DataFrame({"order_id": [1]})
        schema = [
            {"name": "order_id", "type": "INTEGER"},
            {"name": "missing_col", "type": "VARCHAR"},
        ]
        result = checker.check_schema(df, schema)
        assert not result.passed
        assert "missing_col" in result.details


class TestRowCountCheck:
    """Tests for row count check."""

    def test_sufficient_rows(
        self, checker: QualityChecker, sample_df: pd.DataFrame
    ) -> None:
        """DataFrame with enough rows passes."""
        result = checker.check_row_count(sample_df, min_rows=1)
        assert result.passed

    def test_insufficient_rows(self, checker: QualityChecker) -> None:
        """DataFrame below threshold fails."""
        df = pd.DataFrame({"a": []})
        result = checker.check_row_count(df, min_rows=1)
        assert not result.passed


class TestNullCheck:
    """Tests for null value check."""

    def test_no_nulls_passes(
        self, checker: QualityChecker, sample_df: pd.DataFrame
    ) -> None:
        """DataFrame without nulls passes."""
        result = checker.check_nulls(sample_df, ["order_id", "amount"])
        assert result.passed

    def test_nulls_detected(self, checker: QualityChecker) -> None:
        """DataFrame with nulls in checked columns fails."""
        df = pd.DataFrame({"col": [1, None, 3]})
        result = checker.check_nulls(df, ["col"], max_null_pct=0.0)
        assert not result.passed

    def test_empty_df_passes(self, checker: QualityChecker) -> None:
        """Empty DataFrame passes null check."""
        result = checker.check_nulls(pd.DataFrame(), ["col"])
        assert result.passed


class TestDuplicateCheck:
    """Tests for duplicate detection."""

    def test_no_duplicates_passes(
        self, checker: QualityChecker, sample_df: pd.DataFrame
    ) -> None:
        """Unique data passes duplicate check."""
        result = checker.check_duplicates(sample_df, ["order_id"])
        assert result.passed

    def test_duplicates_detected(self, checker: QualityChecker) -> None:
        """Duplicate keys are detected."""
        df = pd.DataFrame({"id": [1, 1, 2]})
        result = checker.check_duplicates(df, ["id"])
        assert not result.passed
        assert "1 duplicate" in result.details

    def test_empty_df_passes(self, checker: QualityChecker) -> None:
        """Empty DataFrame passes."""
        result = checker.check_duplicates(pd.DataFrame(), ["id"])
        assert result.passed

    def test_missing_key_columns(self, checker: QualityChecker) -> None:
        """Missing key columns fails."""
        df = pd.DataFrame({"other": [1, 2]})
        result = checker.check_duplicates(df, ["nonexistent"])
        assert not result.passed


class TestFreshnessCheck:
    """Tests for data freshness check."""

    def test_fresh_data_passes(self, checker: QualityChecker) -> None:
        """Recent data passes freshness check."""
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"ts": [now.isoformat()]})
        result = checker.check_freshness(df, "ts", max_hours=24)
        assert result.passed

    def test_stale_data_fails(self, checker: QualityChecker) -> None:
        """Old data fails freshness check."""
        old = datetime.now(timezone.utc) - timedelta(hours=48)
        df = pd.DataFrame({"ts": [old.isoformat()]})
        result = checker.check_freshness(df, "ts", max_hours=24)
        assert not result.passed

    def test_empty_df_passes(self, checker: QualityChecker) -> None:
        """Empty DataFrame passes freshness check."""
        result = checker.check_freshness(pd.DataFrame(), "ts")
        assert result.passed


class TestMetricBoundsCheck:
    """Tests for metric bounds check."""

    def test_within_bounds_passes(self, checker: QualityChecker) -> None:
        """Values within bounds pass."""
        df = pd.DataFrame({"amount": [10.0, 50.0, 100.0]})
        result = checker.check_metric_bounds(df, "amount", min_value=0, max_value=200)
        assert result.passed

    def test_below_min_fails(self, checker: QualityChecker) -> None:
        """Values below minimum fail."""
        df = pd.DataFrame({"amount": [-5.0, 10.0]})
        result = checker.check_metric_bounds(df, "amount", min_value=0)
        assert not result.passed

    def test_above_max_fails(self, checker: QualityChecker) -> None:
        """Values above maximum fail."""
        df = pd.DataFrame({"amount": [10.0, 999999.0]})
        result = checker.check_metric_bounds(df, "amount", max_value=1000)
        assert not result.passed

    def test_empty_df_passes(self, checker: QualityChecker) -> None:
        """Empty DataFrame passes."""
        result = checker.check_metric_bounds(pd.DataFrame(), "amount")
        assert result.passed


class TestSuiteChecks:
    """Tests for combined check suites."""

    def test_source_checks(
        self, checker: QualityChecker, sample_df: pd.DataFrame, schema: list
    ) -> None:
        """Source checks return list of results."""
        results = checker.run_source_checks(sample_df, schema)
        assert len(results) == 3
        assert all(r.passed for r in results)

    def test_staging_checks(
        self, checker: QualityChecker, sample_df: pd.DataFrame
    ) -> None:
        """Staging checks return list of results."""
        results = checker.run_staging_checks(
            sample_df, ["order_id"], timestamp_column="order_date"
        )
        assert len(results) == 2

    def test_mart_checks(
        self, checker: QualityChecker, sample_df: pd.DataFrame
    ) -> None:
        """Mart checks return list of results."""
        results = checker.run_mart_checks(
            sample_df, metric_column="amount", min_value=0, max_value=100
        )
        assert len(results) == 2
        assert all(r.passed for r in results)
