"""Tests for the dbt runner module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.dbt_runner import DbtRunner


class TestDbtRunner:
    """Tests for DbtRunner command execution."""

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_run_executes_dbt_run(self, mock_run: MagicMock) -> None:
        """dbt run command is executed correctly."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Success", stderr=""
        )

        runner = DbtRunner()
        result = runner.run()

        assert result.returncode == 0
        cmd = mock_run.call_args[0][0]
        assert "dbt" in cmd
        assert "run" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_run_with_select(self, mock_run: MagicMock) -> None:
        """dbt run passes --select argument."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        runner.run(select="staging")

        cmd = mock_run.call_args[0][0]
        assert "--select" in cmd
        assert "staging" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_test_executes_dbt_test(self, mock_run: MagicMock) -> None:
        """dbt test command is executed correctly."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        result = runner.test()

        assert result.returncode == 0
        cmd = mock_run.call_args[0][0]
        assert "test" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_build_executes_dbt_build(self, mock_run: MagicMock) -> None:
        """dbt build command is executed correctly."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        result = runner.build()

        assert result.returncode == 0
        cmd = mock_run.call_args[0][0]
        assert "build" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_docs_generate(self, mock_run: MagicMock) -> None:
        """dbt docs generate command is executed correctly."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        result = runner.docs_generate()

        assert result.returncode == 0
        cmd = mock_run.call_args[0][0]
        assert "docs" in cmd
        assert "generate" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_snapshot_executes_dbt_snapshot(self, mock_run: MagicMock) -> None:
        """dbt snapshot command is executed correctly."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        result = runner.snapshot()

        assert result.returncode == 0
        cmd = mock_run.call_args[0][0]
        assert "snapshot" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_snapshot_with_select(self, mock_run: MagicMock) -> None:
        """dbt snapshot passes --select argument."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        runner.snapshot(select="snap_customers")

        cmd = mock_run.call_args[0][0]
        assert "--select" in cmd
        assert "snap_customers" in cmd

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_failure_logged(self, mock_run: MagicMock) -> None:
        """Failed dbt command returns non-zero exit code."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error"
        )

        runner = DbtRunner()
        result = runner.run()

        assert result.returncode == 1

    def test_custom_project_dir(self, tmp_path: Path) -> None:
        """Custom project directory is used."""
        runner = DbtRunner(project_dir=tmp_path)
        assert runner.project_dir == tmp_path

    @patch("src.utils.dbt_runner.subprocess.run")
    def test_includes_project_and_profiles_dir(self, mock_run: MagicMock) -> None:
        """Command includes --project-dir and --profiles-dir flags."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        runner = DbtRunner()
        runner.run()

        cmd = mock_run.call_args[0][0]
        assert "--project-dir" in cmd
        assert "--profiles-dir" in cmd
