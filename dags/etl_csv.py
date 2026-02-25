"""Airflow DAG for CSV source extraction pipeline.

Extracts order data from CSV files, validates schema,
and loads into DuckDB staging tables.
"""

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator

    _AIRFLOW_AVAILABLE = True
except ImportError:
    _AIRFLOW_AVAILABLE = False

DAG_ID = "etl_csv_orders"
SCHEDULE_INTERVAL = "@daily"

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2024, 1, 1),
}


def extract_csv_task(**kwargs: dict) -> dict:
    """Airflow task to run the CSV extraction pipeline.

    Args:
        kwargs: Airflow context.

    Returns:
        Pipeline execution summary.
    """
    from src.pipelines.etl_pipeline import run_csv_pipeline

    return run_csv_pipeline(source_name="csv_orders")


if _AIRFLOW_AVAILABLE:
    dag = DAG(
        dag_id=DAG_ID,
        default_args=DEFAULT_ARGS,
        schedule_interval=SCHEDULE_INTERVAL,
        catchup=False,
        tags=["etl", "csv"],
    )

    extract_load = PythonOperator(
        task_id="extract_validate_load_csv",
        python_callable=extract_csv_task,
        dag=dag,
    )
