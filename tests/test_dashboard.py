"""Tests for the ETL pipeline dashboard data generators."""

import pandas as pd

from src.dashboard.app import (
    generate_data_volumes,
    generate_failure_log,
    generate_pipeline_runs,
    generate_task_durations,
)


class TestPipelineRuns:
    def test_returns_dataframe(self) -> None:
        df = generate_pipeline_runs()
        assert isinstance(df, pd.DataFrame)

    def test_has_entries(self) -> None:
        df = generate_pipeline_runs()
        assert len(df) > 0

    def test_valid_statuses(self) -> None:
        df = generate_pipeline_runs()
        assert set(df["status"].unique()).issubset({"success", "failed"})

    def test_has_both_statuses(self) -> None:
        df = generate_pipeline_runs()
        assert "success" in df["status"].values
        assert "failed" in df["status"].values

    def test_duration_positive(self) -> None:
        df = generate_pipeline_runs()
        assert (df["duration_min"] > 0).all()

    def test_reproducible(self) -> None:
        df1 = generate_pipeline_runs(seed=99)
        df2 = generate_pipeline_runs(seed=99)
        pd.testing.assert_frame_equal(df1, df2)


class TestTaskDurations:
    def test_returns_dataframe(self) -> None:
        df = generate_task_durations()
        assert isinstance(df, pd.DataFrame)

    def test_has_seven_tasks(self) -> None:
        df = generate_task_durations()
        assert len(df) == 7

    def test_durations_positive(self) -> None:
        df = generate_task_durations()
        assert (df["avg_duration_min"] > 0).all()

    def test_failure_rate_bounded(self) -> None:
        df = generate_task_durations()
        assert (df["failure_rate"] >= 0).all()
        assert (df["failure_rate"] <= 1).all()


class TestDataVolumes:
    def test_returns_dataframe(self) -> None:
        df = generate_data_volumes()
        assert isinstance(df, pd.DataFrame)

    def test_has_entries(self) -> None:
        df = generate_data_volumes()
        assert len(df) == 90  # 30 days x 3 tables

    def test_row_count_positive(self) -> None:
        df = generate_data_volumes()
        assert (df["row_count"] > 0).all()

    def test_three_tables(self) -> None:
        df = generate_data_volumes()
        assert df["table"].nunique() == 3


class TestFailureLog:
    def test_returns_dataframe(self) -> None:
        df = generate_failure_log()
        assert isinstance(df, pd.DataFrame)

    def test_has_entries(self) -> None:
        df = generate_failure_log()
        assert len(df) == 8

    def test_valid_severities(self) -> None:
        df = generate_failure_log()
        assert set(df["severity"].unique()).issubset({"WARNING", "ERROR", "CRITICAL"})

    def test_sorted_by_timestamp(self) -> None:
        df = generate_failure_log()
        assert df["timestamp"].is_monotonic_decreasing
