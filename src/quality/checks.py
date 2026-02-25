"""Data quality checks for source, staging, and mart layers.

Implements validation checks at each stage of the ETL pipeline
including schema validation, freshness checks, duplicate detection,
and business rule enforcement.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

from src.utils.config import load_quality_rules

logger = logging.getLogger(__name__)


class QualityCheckResult:
    """Result of a single quality check.

    Args:
        check_name: Name of the quality check.
        passed: Whether the check passed.
        severity: Check severity (critical, warning).
        details: Optional descriptive details about the result.
    """

    def __init__(
        self,
        check_name: str,
        passed: bool,
        severity: str = "warning",
        details: Optional[str] = None,
    ) -> None:
        self.check_name = check_name
        self.passed = passed
        self.severity = severity
        self.details = details
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a dictionary.

        Returns:
            Dictionary representation of the check result.
        """
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class QualityChecker:
    """Run data quality checks across pipeline stages.

    Loads quality rules from configuration and provides methods
    for source, staging, and mart level validation.
    """

    def __init__(self) -> None:
        try:
            config = load_quality_rules()
            self.rules = config.get("quality_rules", {})
        except FileNotFoundError:
            self.rules = {}
            logger.warning("Quality rules config not found, using defaults")

    def check_schema(
        self,
        df: pd.DataFrame,
        expected_schema: list[dict[str, Any]],
    ) -> QualityCheckResult:
        """Validate DataFrame columns match expected schema.

        Args:
            df: DataFrame to validate.
            expected_schema: List of column definitions with name and type.

        Returns:
            QualityCheckResult indicating pass/fail.
        """
        expected_cols = {col["name"] for col in expected_schema}
        actual_cols = set(df.columns)
        missing = expected_cols - actual_cols

        if missing:
            return QualityCheckResult(
                "schema_validation",
                passed=False,
                severity="critical",
                details=f"Missing columns: {sorted(missing)}",
            )

        return QualityCheckResult(
            "schema_validation",
            passed=True,
            severity="critical",
        )

    def check_row_count(
        self,
        df: pd.DataFrame,
        min_rows: int = 1,
    ) -> QualityCheckResult:
        """Verify DataFrame has at least the minimum number of rows.

        Args:
            df: DataFrame to check.
            min_rows: Minimum required row count.

        Returns:
            QualityCheckResult indicating pass/fail.
        """
        count = len(df)
        passed = count >= min_rows

        return QualityCheckResult(
            "row_count_check",
            passed=passed,
            severity="warning",
            details=f"Row count: {count}, minimum: {min_rows}",
        )

    def check_nulls(
        self,
        df: pd.DataFrame,
        columns: list[str],
        max_null_pct: float = 0.0,
    ) -> QualityCheckResult:
        """Check null percentage in specified columns.

        Args:
            df: DataFrame to check.
            columns: Columns to check for nulls.
            max_null_pct: Maximum allowed null percentage (0.0 to 1.0).

        Returns:
            QualityCheckResult indicating pass/fail.
        """
        if df.empty:
            return QualityCheckResult("null_check", passed=True, severity="critical")

        violations = []
        for col in columns:
            if col not in df.columns:
                continue
            null_pct = df[col].isna().mean()
            if null_pct > max_null_pct:
                violations.append(f"{col}: {null_pct:.1%} null")

        if violations:
            return QualityCheckResult(
                "null_check",
                passed=False,
                severity="critical",
                details=f"Null violations: {', '.join(violations)}",
            )

        return QualityCheckResult("null_check", passed=True, severity="critical")

    def check_duplicates(
        self,
        df: pd.DataFrame,
        key_columns: list[str],
    ) -> QualityCheckResult:
        """Detect duplicate rows based on key columns.

        Args:
            df: DataFrame to check.
            key_columns: Columns that should form a unique key.

        Returns:
            QualityCheckResult indicating pass/fail.
        """
        if df.empty:
            return QualityCheckResult(
                "duplicate_check", passed=True, severity="critical"
            )

        existing_cols = [c for c in key_columns if c in df.columns]
        if not existing_cols:
            return QualityCheckResult(
                "duplicate_check",
                passed=False,
                severity="critical",
                details="No key columns found in DataFrame",
            )

        dup_count = df.duplicated(subset=existing_cols).sum()

        if dup_count > 0:
            return QualityCheckResult(
                "duplicate_check",
                passed=False,
                severity="critical",
                details=f"{dup_count} duplicate rows on keys {existing_cols}",
            )

        return QualityCheckResult("duplicate_check", passed=True, severity="critical")

    def check_freshness(
        self,
        df: pd.DataFrame,
        timestamp_column: str,
        max_hours: int = 24,
    ) -> QualityCheckResult:
        """Check if data is fresh enough based on a timestamp column.

        Args:
            df: DataFrame to check.
            timestamp_column: Column containing timestamps.
            max_hours: Maximum age in hours for data to be considered fresh.

        Returns:
            QualityCheckResult indicating pass/fail.
        """
        if df.empty or timestamp_column not in df.columns:
            return QualityCheckResult(
                "freshness_check",
                passed=True,
                severity="warning",
                details="No data or timestamp column not found",
            )

        latest = pd.to_datetime(df[timestamp_column]).max()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
        cutoff = pd.Timestamp(cutoff)

        if latest.tzinfo is None:
            latest = latest.tz_localize("UTC")

        passed = latest >= cutoff

        return QualityCheckResult(
            "freshness_check",
            passed=passed,
            severity="warning",
            details=f"Latest record: {latest}, cutoff: {cutoff}",
        )

    def check_metric_bounds(
        self,
        df: pd.DataFrame,
        column: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> QualityCheckResult:
        """Check if column values fall within expected bounds.

        Args:
            df: DataFrame to check.
            column: Column to validate.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.

        Returns:
            QualityCheckResult indicating pass/fail.
        """
        if df.empty or column not in df.columns:
            return QualityCheckResult(
                "metric_bounds_check", passed=True, severity="warning"
            )

        violations = []
        col_vals = pd.to_numeric(df[column], errors="coerce")

        if min_value is not None and col_vals.min() < min_value:
            violations.append(f"Min value {col_vals.min()} < {min_value}")

        if max_value is not None and col_vals.max() > max_value:
            violations.append(f"Max value {col_vals.max()} > {max_value}")

        if violations:
            return QualityCheckResult(
                "metric_bounds_check",
                passed=False,
                severity="warning",
                details="; ".join(violations),
            )

        return QualityCheckResult(
            "metric_bounds_check", passed=True, severity="warning"
        )

    def run_source_checks(
        self,
        df: pd.DataFrame,
        schema: list[dict[str, Any]],
    ) -> list[QualityCheckResult]:
        """Run all source-level quality checks.

        Args:
            df: Extracted source DataFrame.
            schema: Expected column schema.

        Returns:
            List of QualityCheckResult objects.
        """
        non_nullable = [col["name"] for col in schema if not col.get("nullable", True)]

        results = [
            self.check_schema(df, schema),
            self.check_row_count(df),
            self.check_nulls(df, non_nullable),
        ]

        for r in results:
            status = "PASS" if r.passed else "FAIL"
            logger.info("Source check [%s] %s: %s", r.check_name, status, r.details)

        return results

    def run_staging_checks(
        self,
        df: pd.DataFrame,
        key_columns: list[str],
        timestamp_column: Optional[str] = None,
    ) -> list[QualityCheckResult]:
        """Run all staging-level quality checks.

        Args:
            df: Staged DataFrame.
            key_columns: Primary key columns for duplicate detection.
            timestamp_column: Optional timestamp column for freshness checks.

        Returns:
            List of QualityCheckResult objects.
        """
        results = [self.check_duplicates(df, key_columns)]

        if timestamp_column:
            results.append(self.check_freshness(df, timestamp_column))

        for r in results:
            status = "PASS" if r.passed else "FAIL"
            logger.info("Staging check [%s] %s: %s", r.check_name, status, r.details)

        return results

    def run_mart_checks(
        self,
        df: pd.DataFrame,
        metric_column: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> list[QualityCheckResult]:
        """Run all mart-level quality checks.

        Args:
            df: Mart DataFrame.
            metric_column: Column to check bounds on.
            min_value: Minimum allowed metric value.
            max_value: Maximum allowed metric value.

        Returns:
            List of QualityCheckResult objects.
        """
        results = [self.check_row_count(df)]

        if metric_column:
            results.append(
                self.check_metric_bounds(df, metric_column, min_value, max_value)
            )

        for r in results:
            status = "PASS" if r.passed else "FAIL"
            logger.info("Mart check [%s] %s: %s", r.check_name, status, r.details)

        return results
