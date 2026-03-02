"""Streamlit dashboard for ETL pipeline monitoring.

Displays pipeline run status, task duration trends, data volume
tracking, and failure analysis using synthetic demo data.

Run with: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def generate_pipeline_runs(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic pipeline run history."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-11-01", periods=30, freq="D")
    rows = []
    for date in dates:
        num_runs = int(rng.integers(3, 8))
        for run_id in range(num_runs):
            status = rng.choice(["success", "failed", "success", "success", "success"])
            rows.append(
                {
                    "date": date,
                    "run_id": f"dag_{date.strftime('%m%d')}_{run_id}",
                    "status": status,
                    "duration_min": round(rng.uniform(5, 120), 1),
                    "records_processed": int(rng.integers(10000, 500000)),
                }
            )
    return pd.DataFrame(rows)


def generate_task_durations(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic task duration breakdown."""
    rng = np.random.default_rng(seed)
    tasks = [
        "extract_csv",
        "extract_api",
        "extract_db",
        "load_staging",
        "transform_dbt",
        "quality_checks",
        "publish_warehouse",
    ]
    rows = []
    for task in tasks:
        rows.append(
            {
                "task": task,
                "avg_duration_min": round(rng.uniform(2, 30), 1),
                "p95_duration_min": round(rng.uniform(10, 60), 1),
                "failure_rate": round(rng.uniform(0.0, 0.15), 4),
            }
        )
    return pd.DataFrame(rows)


def generate_data_volumes(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic data volume trends."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-11-01", periods=30, freq="D")
    tables = ["customers", "transactions", "events"]
    rows = []
    for date in dates:
        for table in tables:
            base = {"customers": 5000, "transactions": 50000, "events": 100000}[table]
            rows.append(
                {
                    "date": date,
                    "table": table,
                    "row_count": int(base + rng.integers(-base // 5, base // 3)),
                    "size_mb": round(rng.uniform(10, 500), 1),
                }
            )
    return pd.DataFrame(rows)


def generate_failure_log(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic failure log entries."""
    rng = np.random.default_rng(seed)
    errors = [
        "Connection timeout to source DB",
        "API rate limit exceeded",
        "Schema validation failed: missing column 'email'",
        "DuckDB load error: type mismatch on 'amount'",
        "dbt test failed: not_null on orders.customer_id",
        "Quality check failed: null_rate > 5%",
    ]
    rows = []
    for i in range(8):
        rows.append(
            {
                "timestamp": pd.Timestamp("2024-11-28")
                - pd.Timedelta(hours=int(rng.integers(1, 720))),
                "task": rng.choice(
                    ["extract_api", "extract_db", "transform_dbt", "quality_checks"]
                ),
                "error": rng.choice(errors),
                "severity": rng.choice(["WARNING", "ERROR", "CRITICAL"]),
            }
        )
    return pd.DataFrame(rows).sort_values("timestamp", ascending=False)


def render_header() -> None:
    """Render the dashboard header."""
    st.title("ETL Pipeline Monitoring Dashboard")
    st.caption(
        "Airflow-based ETL orchestration with DuckDB warehouse, "
        "dbt transforms, and data quality monitoring"
    )


def render_summary_metrics(runs_df: pd.DataFrame) -> None:
    """Render top-level summary metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", len(runs_df))
    success_rate = (runs_df["status"] == "success").mean()
    col2.metric("Success Rate", f"{success_rate:.0%}")
    col3.metric("Avg Duration", f"{runs_df['duration_min'].mean():.1f} min")
    col4.metric("Records Today", f"{runs_df['records_processed'].sum():,}")


def render_run_timeline(runs_df: pd.DataFrame) -> None:
    """Render daily run status timeline."""
    st.subheader("Daily Pipeline Runs")
    daily = runs_df.groupby(["date", "status"]).size().reset_index(name="count")
    fig = px.bar(
        daily,
        x="date",
        y="count",
        color="status",
        color_discrete_map={"success": "#4CAF50", "failed": "#F44336"},
    )
    fig.update_layout(
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_task_durations(task_df: pd.DataFrame) -> None:
    """Render task duration comparison chart."""
    st.subheader("Task Duration Breakdown")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Avg Duration",
            x=task_df["task"],
            y=task_df["avg_duration_min"],
            text=task_df["avg_duration_min"].apply(lambda x: f"{x:.1f}m"),
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            name="P95 Duration",
            x=task_df["task"],
            y=task_df["p95_duration_min"],
            text=task_df["p95_duration_min"].apply(lambda x: f"{x:.1f}m"),
            textposition="auto",
        )
    )
    fig.update_layout(
        barmode="group",
        yaxis_title="Duration (min)",
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 80},
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_data_volumes(vol_df: pd.DataFrame) -> None:
    """Render data volume trends."""
    st.subheader("Data Volume Trends")
    fig = px.line(
        vol_df,
        x="date",
        y="row_count",
        color="table",
        markers=True,
    )
    fig.update_layout(
        yaxis_title="Row Count",
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_failure_log(fail_df: pd.DataFrame) -> None:
    """Render recent failure log."""
    st.subheader("Recent Failures")
    st.dataframe(fail_df, use_container_width=True, hide_index=True)


def main() -> None:
    """Main dashboard entry point."""
    render_header()

    runs_df = generate_pipeline_runs()
    task_df = generate_task_durations()
    vol_df = generate_data_volumes()
    fail_df = generate_failure_log()

    render_summary_metrics(runs_df)
    st.markdown("---")

    render_run_timeline(runs_df)

    col_left, col_right = st.columns(2)
    with col_left:
        render_task_durations(task_df)
    with col_right:
        render_data_volumes(vol_df)

    st.markdown("---")
    render_failure_log(fail_df)


if __name__ == "__main__":
    main()
