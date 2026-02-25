"""Tests for Docker Compose configuration validation."""

from pathlib import Path

import yaml


def _load_compose() -> dict:
    """Load and parse the docker-compose.yml file."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    with open(compose_path) as f:
        return yaml.safe_load(f)


class TestDockerComposeServices:
    """Tests for Docker Compose service definitions."""

    def test_compose_loads_valid_yaml(self) -> None:
        """docker-compose.yml is valid YAML."""
        config = _load_compose()
        assert isinstance(config, dict)

    def test_postgres_service_defined(self) -> None:
        """Postgres service exists with healthcheck."""
        config = _load_compose()
        postgres = config["services"]["postgres"]
        assert postgres["image"] == "postgres:15"
        assert "healthcheck" in postgres

    def test_airflow_init_service_defined(self) -> None:
        """Airflow init service exists for database migration."""
        config = _load_compose()
        assert "airflow-init" in config["services"]

    def test_airflow_webserver_service_defined(self) -> None:
        """Airflow webserver is exposed on port 8080."""
        config = _load_compose()
        webserver = config["services"]["airflow-webserver"]
        assert "8080:8080" in webserver["ports"]
        assert "healthcheck" in webserver

    def test_airflow_scheduler_service_defined(self) -> None:
        """Airflow scheduler is configured."""
        config = _load_compose()
        scheduler = config["services"]["airflow-scheduler"]
        assert scheduler["command"] == "scheduler"

    def test_mock_api_service_defined(self) -> None:
        """Mock API service is exposed on port 5000."""
        config = _load_compose()
        mock_api = config["services"]["mock-api"]
        assert "5000:5000" in mock_api["ports"]
        assert "healthcheck" in mock_api

    def test_postgres_volume_defined(self) -> None:
        """Persistent volume for PostgreSQL data exists."""
        config = _load_compose()
        assert "postgres-db" in config.get("volumes", {})


class TestDockerComposeEnvironment:
    """Tests for environment configuration."""

    def test_airflow_executor_configured(self) -> None:
        """Airflow uses LocalExecutor."""
        config = _load_compose()
        env = config.get("x-airflow-common", {}).get("environment", {})
        assert env.get("AIRFLOW__CORE__EXECUTOR") == "LocalExecutor"

    def test_pythonpath_set(self) -> None:
        """PYTHONPATH is set for module imports."""
        config = _load_compose()
        env = config.get("x-airflow-common", {}).get("environment", {})
        assert "PYTHONPATH" in env

    def test_duckdb_path_set(self) -> None:
        """DuckDB path is configured."""
        config = _load_compose()
        env = config.get("x-airflow-common", {}).get("environment", {})
        assert "DUCKDB_PATH" in env


class TestDockerComposeVolumes:
    """Tests for volume mount configuration."""

    def test_dags_mounted(self) -> None:
        """DAGs directory is mounted."""
        config = _load_compose()
        volumes = config.get("x-airflow-common", {}).get("volumes", [])
        dag_mounts = [v for v in volumes if "/dags" in v]
        assert len(dag_mounts) >= 1

    def test_src_mounted(self) -> None:
        """Source code directory is mounted."""
        config = _load_compose()
        volumes = config.get("x-airflow-common", {}).get("volumes", [])
        src_mounts = [v for v in volumes if "/src" in v]
        assert len(src_mounts) >= 1

    def test_configs_mounted(self) -> None:
        """Configs directory is mounted."""
        config = _load_compose()
        volumes = config.get("x-airflow-common", {}).get("volumes", [])
        config_mounts = [v for v in volumes if "/configs" in v]
        assert len(config_mounts) >= 1


class TestDockerfiles:
    """Tests for Dockerfile existence."""

    def test_airflow_dockerfile_exists(self) -> None:
        """Dockerfile.airflow exists."""
        path = Path(__file__).parent.parent / "Dockerfile.airflow"
        assert path.exists()

    def test_mock_api_dockerfile_exists(self) -> None:
        """Mock API Dockerfile exists."""
        path = Path(__file__).parent.parent / "mock_api" / "Dockerfile"
        assert path.exists()

    def test_main_dockerfile_exists(self) -> None:
        """Main Dockerfile exists."""
        path = Path(__file__).parent.parent / "Dockerfile"
        assert path.exists()
