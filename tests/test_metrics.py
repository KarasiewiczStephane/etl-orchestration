"""Tests for the pipeline metrics collection module."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.monitoring.metrics import MetricsCollector


@pytest.fixture()
def collector(tmp_path: Path) -> MetricsCollector:
    """Create a MetricsCollector with temp database."""
    return MetricsCollector(db_path=tmp_path / "metrics.db")


def _make_run(
    collector: MetricsCollector,
    run_id: str = "run_001",
    dag_id: str = "etl_csv",
    task_id: str = "extract",
    status: str = "success",
    duration_seconds: float = 10.0,
    rows: int = 100,
    error: str | None = None,
) -> None:
    """Helper to log a task run with computed timestamps."""
    now = datetime.now(timezone.utc)
    collector.log_task_run(
        run_id=run_id,
        dag_id=dag_id,
        task_id=task_id,
        status=status,
        started_at=now - timedelta(seconds=duration_seconds),
        completed_at=now,
        rows_processed=rows,
        error_message=error,
    )


class TestMetricsCollectorLogRun:
    """Tests for logging task runs."""

    def test_log_task_run(self, collector: MetricsCollector) -> None:
        """Task run is logged without error."""
        _make_run(collector)

    def test_log_multiple_tasks(self, collector: MetricsCollector) -> None:
        """Multiple tasks in a run are logged."""
        _make_run(collector, task_id="extract")
        _make_run(collector, task_id="load")
        metrics = collector.get_pipeline_metrics("etl_csv")
        assert metrics.total_runs == 1

    def test_log_failed_run(self, collector: MetricsCollector) -> None:
        """Failed task run with error message is logged."""
        _make_run(
            collector,
            status="failed",
            error="Connection timeout",
        )
        failures = collector.get_recent_failures()
        assert len(failures) == 1
        assert failures[0]["error_message"] == "Connection timeout"


class TestMetricsCollectorPipelineMetrics:
    """Tests for aggregated pipeline metrics."""

    def test_empty_metrics(self, collector: MetricsCollector) -> None:
        """No data returns zero metrics."""
        metrics = collector.get_pipeline_metrics("nonexistent")
        assert metrics.total_runs == 0
        assert metrics.success_rate == 0.0

    def test_success_rate_calculation(self, collector: MetricsCollector) -> None:
        """Success rate is calculated correctly."""
        _make_run(collector, run_id="r1", task_id="t1", status="success")
        _make_run(collector, run_id="r2", task_id="t2", status="success")
        _make_run(collector, run_id="r3", task_id="t3", status="failed")
        metrics = collector.get_pipeline_metrics("etl_csv")
        assert metrics.successful_runs == 2
        assert metrics.failed_runs == 1

    def test_rows_processed_summed(self, collector: MetricsCollector) -> None:
        """Total rows processed is summed across runs."""
        _make_run(collector, run_id="r1", task_id="t1", rows=100)
        _make_run(collector, run_id="r2", task_id="t2", rows=200)
        metrics = collector.get_pipeline_metrics("etl_csv")
        assert metrics.total_rows_processed == 300

    def test_avg_duration(self, collector: MetricsCollector) -> None:
        """Average duration is calculated."""
        _make_run(collector, run_id="r1", task_id="t1", duration_seconds=10.0)
        _make_run(collector, run_id="r2", task_id="t2", duration_seconds=20.0)
        metrics = collector.get_pipeline_metrics("etl_csv")
        assert metrics.avg_duration_seconds == pytest.approx(15.0, abs=0.5)

    def test_metrics_to_dict(self, collector: MetricsCollector) -> None:
        """PipelineMetrics converts to dict."""
        _make_run(collector)
        metrics = collector.get_pipeline_metrics("etl_csv")
        d = metrics.to_dict()
        assert d["dag_id"] == "etl_csv"
        assert "success_rate" in d


class TestMetricsCollectorTrend:
    """Tests for trend data queries."""

    def test_trend_data_empty(self, collector: MetricsCollector) -> None:
        """No data returns empty trend list."""
        trends = collector.get_trend_data("nonexistent")
        assert trends == []

    def test_trend_data_grouped_by_day(self, collector: MetricsCollector) -> None:
        """Runs on the same day are grouped."""
        _make_run(collector, run_id="r1", task_id="t1")
        _make_run(collector, run_id="r2", task_id="t2")
        trends = collector.get_trend_data("etl_csv")
        assert len(trends) == 1
        assert trends[0]["runs"] >= 1


class TestMetricsCollectorDataVolumes:
    """Tests for data volume tracking."""

    def test_log_and_query_volume(self, collector: MetricsCollector) -> None:
        """Volume snapshot is recorded and queried."""
        collector.log_data_volume("staging.orders", 1000, 4096)
        volumes = collector.get_data_volumes("staging.orders")
        assert len(volumes) == 1
        assert volumes[0]["row_count"] == 1000
        assert volumes[0]["size_bytes"] == 4096

    def test_query_all_volumes(self, collector: MetricsCollector) -> None:
        """All volumes returned without filter."""
        collector.log_data_volume("staging.orders", 100)
        collector.log_data_volume("mart.summary", 50)
        volumes = collector.get_data_volumes()
        assert len(volumes) == 2

    def test_volume_limit(self, collector: MetricsCollector) -> None:
        """Limit parameter constrains results."""
        for i in range(10):
            collector.log_data_volume(f"table_{i}", i * 10)
        volumes = collector.get_data_volumes(limit=3)
        assert len(volumes) == 3


class TestMetricsCollectorFailures:
    """Tests for recent failure queries."""

    def test_no_failures(self, collector: MetricsCollector) -> None:
        """No failures returns empty list."""
        _make_run(collector, status="success")
        failures = collector.get_recent_failures()
        assert failures == []

    def test_failures_returned(self, collector: MetricsCollector) -> None:
        """Failed runs are returned."""
        _make_run(
            collector,
            run_id="r1",
            task_id="t1",
            status="failed",
            error="timeout",
        )
        _make_run(
            collector,
            run_id="r2",
            task_id="t2",
            status="failed",
            error="connection lost",
        )
        failures = collector.get_recent_failures()
        assert len(failures) == 2


class TestMetricsCollectorReport:
    """Tests for report generation."""

    def test_empty_report(self, collector: MetricsCollector) -> None:
        """Empty database produces informative message."""
        report = collector.generate_report()
        assert "No pipeline metrics" in report

    def test_report_contains_pipeline(self, collector: MetricsCollector) -> None:
        """Report includes pipeline name and metrics."""
        _make_run(collector)
        report = collector.generate_report()
        assert "etl_csv" in report
        assert "Success Rate" in report

    def test_report_with_failures(self, collector: MetricsCollector) -> None:
        """Report includes failure details."""
        _make_run(
            collector,
            status="failed",
            error="data corrupt",
        )
        report = collector.generate_report()
        assert "Recent Failures" in report
        assert "data corrupt" in report

    def test_report_specific_dags(self, collector: MetricsCollector) -> None:
        """Report filters to specified DAGs."""
        _make_run(collector, dag_id="etl_csv", task_id="t1")
        _make_run(collector, dag_id="etl_api", task_id="t2")
        report = collector.generate_report(dag_ids=["etl_csv"])
        assert "etl_csv" in report
        assert "etl_api" not in report
