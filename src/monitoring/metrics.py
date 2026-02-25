"""Pipeline metrics collection and monitoring.

Tracks task durations, success rates, data volumes, and provides
aggregated pipeline metrics for monitoring and reporting.
"""

import logging
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from src.utils.config import load_config

logger = logging.getLogger(__name__)

_DEFAULT_METRICS_DB = "data/metrics.db"


@dataclass
class PipelineMetrics:
    """Aggregated metrics for a pipeline.

    Args:
        dag_id: Pipeline/DAG identifier.
        total_runs: Total number of runs in the period.
        successful_runs: Number of successful runs.
        failed_runs: Number of failed runs.
        avg_duration_seconds: Average task duration in seconds.
        total_rows_processed: Total rows processed across all runs.
        success_rate: Ratio of successful runs to total runs.
    """

    dag_id: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_duration_seconds: float
    total_rows_processed: int
    success_rate: float

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a dictionary.

        Returns:
            Dictionary representation of the pipeline metrics.
        """
        return asdict(self)


class MetricsCollector:
    """Collect and query pipeline execution metrics.

    Stores task run data and data volume snapshots in SQLite
    for aggregation and trend analysis.

    Args:
        db_path: Path to the SQLite metrics database.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            try:
                config = load_config()
                db_path = config.get("paths", {}).get("metrics_db", _DEFAULT_METRICS_DB)
            except FileNotFoundError:
                db_path = _DEFAULT_METRICS_DB

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the metrics database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_runs (
                    run_id TEXT NOT NULL,
                    dag_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    rows_processed INTEGER DEFAULT 0,
                    error_message TEXT,
                    PRIMARY KEY (run_id, task_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS data_volumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    size_bytes INTEGER DEFAULT 0
                )
                """
            )

    def log_task_run(
        self,
        run_id: str,
        dag_id: str,
        task_id: str,
        status: str,
        started_at: datetime,
        completed_at: datetime,
        rows_processed: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a task run execution.

        Args:
            run_id: Unique pipeline run identifier.
            dag_id: Pipeline/DAG identifier.
            task_id: Task identifier within the pipeline.
            status: Run status ('success' or 'failed').
            started_at: Task start timestamp.
            completed_at: Task completion timestamp.
            rows_processed: Number of rows processed.
            error_message: Error message if the task failed.
        """
        duration = (completed_at - started_at).total_seconds()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO task_runs
                    (run_id, dag_id, task_id, status, started_at,
                     completed_at, duration_seconds, rows_processed,
                     error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    dag_id,
                    task_id,
                    status,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    duration,
                    rows_processed,
                    error_message,
                ),
            )

        logger.info(
            "Logged task run: %s/%s status=%s duration=%.1fs",
            dag_id,
            task_id,
            status,
            duration,
        )

    def log_data_volume(
        self,
        table_name: str,
        row_count: int,
        size_bytes: int = 0,
    ) -> None:
        """Record a data volume snapshot for a table.

        Args:
            table_name: Name of the table.
            row_count: Current row count.
            size_bytes: Table size in bytes.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO data_volumes
                    (timestamp, table_name, row_count, size_bytes)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, table_name, row_count, size_bytes),
            )

        logger.info(
            "Logged volume: %s rows=%d size=%d bytes",
            table_name,
            row_count,
            size_bytes,
        )

    def get_pipeline_metrics(
        self,
        dag_id: str,
        days: int = 7,
    ) -> PipelineMetrics:
        """Get aggregated metrics for a pipeline over a time period.

        Args:
            dag_id: Pipeline/DAG identifier.
            days: Number of days to look back.

        Returns:
            Aggregated PipelineMetrics for the pipeline.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT run_id) as total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END),
                    AVG(duration_seconds),
                    SUM(rows_processed)
                FROM task_runs
                WHERE dag_id = ? AND started_at > ?
                """,
                (dag_id, cutoff),
            ).fetchone()

        total = row[0] or 0
        successful = row[1] or 0

        return PipelineMetrics(
            dag_id=dag_id,
            total_runs=total,
            successful_runs=successful,
            failed_runs=row[2] or 0,
            avg_duration_seconds=row[3] or 0.0,
            total_rows_processed=row[4] or 0,
            success_rate=successful / total if total > 0 else 0.0,
        )

    def get_trend_data(
        self,
        dag_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get daily trend data for a pipeline.

        Args:
            dag_id: Pipeline/DAG identifier.
            days: Number of days to look back.

        Returns:
            List of daily aggregation dictionaries.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT
                    DATE(started_at) as date,
                    COUNT(DISTINCT run_id) as runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
                    AVG(duration_seconds)
                FROM task_runs
                WHERE dag_id = ? AND started_at > ?
                GROUP BY DATE(started_at)
                ORDER BY date
                """,
                (dag_id, cutoff),
            ).fetchall()

        return [
            {
                "date": r[0],
                "runs": r[1],
                "successful": r[2],
                "avg_duration": r[3],
            }
            for r in rows
        ]

    def get_data_volumes(
        self,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query data volume snapshots.

        Args:
            table_name: Optional filter by table name.
            limit: Maximum number of records to return.

        Returns:
            List of data volume dictionaries.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if table_name:
                rows = conn.execute(
                    "SELECT * FROM data_volumes WHERE table_name = ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (table_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM data_volumes ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [dict(row) for row in rows]

    def get_recent_failures(
        self,
        days: int = 7,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent task failures.

        Args:
            days: Number of days to look back.
            limit: Maximum number of failures to return.

        Returns:
            List of failed task run dictionaries.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM task_runs
                WHERE status = 'failed' AND started_at > ?
                ORDER BY started_at DESC LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()

        return [dict(row) for row in rows]

    def generate_report(self, dag_ids: Optional[list[str]] = None) -> str:
        """Generate a text-based monitoring report.

        Args:
            dag_ids: Optional list of DAG IDs to report on.
                If None, reports on all known DAGs.

        Returns:
            Formatted text report string.
        """
        if dag_ids is None:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute("SELECT DISTINCT dag_id FROM task_runs").fetchall()
            dag_ids = [r[0] for r in rows]

        if not dag_ids:
            return "No pipeline metrics recorded."

        lines = ["Pipeline Monitoring Report", "=" * 50]

        for dag_id in dag_ids:
            metrics = self.get_pipeline_metrics(dag_id)
            lines.append(f"\n  Pipeline: {metrics.dag_id}")
            lines.append(f"    Total Runs:      {metrics.total_runs}")
            lines.append(f"    Successful:      {metrics.successful_runs}")
            lines.append(f"    Failed:          {metrics.failed_runs}")
            lines.append(f"    Success Rate:    {metrics.success_rate:.1%}")
            lines.append(f"    Avg Duration:    {metrics.avg_duration_seconds:.1f}s")
            lines.append(f"    Rows Processed:  {metrics.total_rows_processed}")

        failures = self.get_recent_failures()
        if failures:
            lines.append(f"\n  Recent Failures ({len(failures)}):")
            for f in failures[:5]:
                lines.append(
                    f"    - [{f['dag_id']}/{f['task_id']}] {f['error_message']}"
                )

        return "\n".join(lines)
