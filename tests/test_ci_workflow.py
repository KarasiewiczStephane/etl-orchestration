"""Tests for GitHub Actions CI workflow configuration."""

from pathlib import Path

import yaml


def _load_workflow(name: str = "ci.yml") -> dict:
    """Load and parse a GitHub Actions workflow file."""
    path = Path(__file__).parent.parent / ".github" / "workflows" / name
    with open(path) as f:
        return yaml.safe_load(f)


class TestCIWorkflowStructure:
    """Tests for CI workflow structure."""

    def test_workflow_loads_valid_yaml(self) -> None:
        """ci.yml is valid YAML."""
        config = _load_workflow()
        assert isinstance(config, dict)

    def test_workflow_has_name(self) -> None:
        """Workflow has a name."""
        config = _load_workflow()
        assert "name" in config

    def test_triggers_on_push_and_pr(self) -> None:
        """Workflow triggers on push and pull request to main."""
        config = _load_workflow()
        # PyYAML parses 'on' as boolean True
        triggers = config[True]
        assert "push" in triggers
        assert "pull_request" in triggers
        assert "main" in triggers["push"]["branches"]
        assert "main" in triggers["pull_request"]["branches"]


class TestCIWorkflowJobs:
    """Tests for CI workflow job definitions."""

    def test_lint_job_exists(self) -> None:
        """Lint job is defined."""
        config = _load_workflow()
        assert "lint" in config["jobs"]

    def test_test_job_exists(self) -> None:
        """Test job is defined."""
        config = _load_workflow()
        assert "test" in config["jobs"]

    def test_dag_validation_job_exists(self) -> None:
        """DAG validation job is defined."""
        config = _load_workflow()
        assert "dag-validation" in config["jobs"]

    def test_quality_gate_job_exists(self) -> None:
        """Quality gate job is defined."""
        config = _load_workflow()
        assert "quality-gate" in config["jobs"]

    def test_test_depends_on_lint(self) -> None:
        """Test job depends on lint."""
        config = _load_workflow()
        assert "lint" in config["jobs"]["test"]["needs"]

    def test_quality_gate_depends_on_all(self) -> None:
        """Quality gate depends on test and dag-validation."""
        config = _load_workflow()
        needs = config["jobs"]["quality-gate"]["needs"]
        assert "test" in needs
        assert "dag-validation" in needs

    def test_all_jobs_use_ubuntu(self) -> None:
        """All jobs run on ubuntu-latest."""
        config = _load_workflow()
        for job_name, job in config["jobs"].items():
            assert (
                job["runs-on"] == "ubuntu-latest"
            ), f"{job_name} should use ubuntu-latest"

    def test_python_version_is_311(self) -> None:
        """Python 3.11 is used across jobs."""
        config = _load_workflow()
        for job in config["jobs"].values():
            for step in job.get("steps", []):
                if step.get("uses", "").startswith("actions/setup-python"):
                    assert step["with"]["python-version"] == "3.11"
