"""Master Airflow DAG that orchestrates all ETL pipelines.

Runs all source extractions, then triggers dbt transformations
and data quality checks in sequence.
"""

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator

    _AIRFLOW_AVAILABLE = True
except ImportError:
    _AIRFLOW_AVAILABLE = False

DAG_ID = "master_orchestration"
SCHEDULE_INTERVAL = "@daily"

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "start_date": datetime(2024, 1, 1),
    "sla": timedelta(hours=2),
}


def run_dbt_transformations(**kwargs: dict) -> dict:
    """Execute dbt run and test.

    Args:
        kwargs: Airflow context.

    Returns:
        dbt execution summary.
    """
    from src.utils.dbt_runner import DbtRunner

    runner = DbtRunner()
    run_result = runner.run()
    test_result = runner.test()

    return {
        "dbt_run_exit": run_result.returncode,
        "dbt_test_exit": test_result.returncode,
    }


def run_dbt_snapshots(**kwargs: dict) -> dict:
    """Execute dbt snapshots for SCD Type 2.

    Args:
        kwargs: Airflow context.

    Returns:
        Snapshot execution summary.
    """
    from src.utils.dbt_runner import DbtRunner

    runner = DbtRunner()
    result = runner.snapshot()

    return {"dbt_snapshot_exit": result.returncode}


if _AIRFLOW_AVAILABLE:
    dag = DAG(
        dag_id=DAG_ID,
        default_args=DEFAULT_ARGS,
        schedule_interval=SCHEDULE_INTERVAL,
        catchup=False,
        tags=["orchestration", "master"],
    )

    trigger_csv = TriggerDagRunOperator(
        task_id="trigger_csv_etl",
        trigger_dag_id="etl_csv_orders",
        wait_for_completion=True,
        dag=dag,
    )

    trigger_api = TriggerDagRunOperator(
        task_id="trigger_api_etl",
        trigger_dag_id="etl_api_transactions",
        wait_for_completion=True,
        dag=dag,
    )

    trigger_db = TriggerDagRunOperator(
        task_id="trigger_db_etl",
        trigger_dag_id="etl_db_customers",
        wait_for_completion=True,
        dag=dag,
    )

    dbt_transform = PythonOperator(
        task_id="dbt_transformations",
        python_callable=run_dbt_transformations,
        dag=dag,
    )

    dbt_snapshot = PythonOperator(
        task_id="dbt_snapshots",
        python_callable=run_dbt_snapshots,
        dag=dag,
    )

    [trigger_csv, trigger_api, trigger_db] >> dbt_transform >> dbt_snapshot
