"""Airflow DAG for API source extraction pipeline.

Extracts transaction data from the REST API, validates schema,
and loads into DuckDB staging tables.
"""

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator

    _AIRFLOW_AVAILABLE = True
except ImportError:
    _AIRFLOW_AVAILABLE = False

DAG_ID = "etl_api_transactions"
SCHEDULE_INTERVAL = "@hourly"

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "start_date": datetime(2024, 1, 1),
}


def extract_api_task(**kwargs: dict) -> dict:
    """Airflow task to run the API extraction pipeline.

    Args:
        kwargs: Airflow context.

    Returns:
        Pipeline execution summary.
    """
    from src.pipelines.etl_pipeline import run_api_pipeline

    return run_api_pipeline(source_name="api_transactions")


if _AIRFLOW_AVAILABLE:
    dag = DAG(
        dag_id=DAG_ID,
        default_args=DEFAULT_ARGS,
        schedule_interval=SCHEDULE_INTERVAL,
        catchup=False,
        tags=["etl", "api"],
    )

    extract_load = PythonOperator(
        task_id="extract_validate_load_api",
        python_callable=extract_api_task,
        dag=dag,
    )
