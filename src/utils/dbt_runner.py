"""dbt project runner for executing transformations.

Provides a Python interface for running dbt commands (run, test, docs)
against the project's dbt_project directory.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from src.utils.config import get_project_root

logger = logging.getLogger(__name__)

_DBT_PROJECT_DIR = "dbt_project"


class DbtRunner:
    """Execute dbt commands against the project's dbt models.

    Args:
        project_dir: Path to the dbt project directory.
        profiles_dir: Path to the directory containing profiles.yml.
    """

    def __init__(
        self,
        project_dir: Optional[str | Path] = None,
        profiles_dir: Optional[str | Path] = None,
    ) -> None:
        root = get_project_root()
        self.project_dir = Path(project_dir) if project_dir else root / _DBT_PROJECT_DIR
        self.profiles_dir = Path(profiles_dir) if profiles_dir else self.project_dir

    def run(self, select: Optional[str] = None) -> subprocess.CompletedProcess:
        """Execute dbt run to materialize models.

        Args:
            select: Optional model selection string (e.g., 'staging').

        Returns:
            CompletedProcess with stdout/stderr.
        """
        cmd = self._build_command("run")
        if select:
            cmd.extend(["--select", select])
        return self._execute(cmd)

    def test(self, select: Optional[str] = None) -> subprocess.CompletedProcess:
        """Execute dbt test to run schema tests.

        Args:
            select: Optional model selection string.

        Returns:
            CompletedProcess with stdout/stderr.
        """
        cmd = self._build_command("test")
        if select:
            cmd.extend(["--select", select])
        return self._execute(cmd)

    def build(self) -> subprocess.CompletedProcess:
        """Execute dbt build (run + test).

        Returns:
            CompletedProcess with stdout/stderr.
        """
        return self._execute(self._build_command("build"))

    def docs_generate(self) -> subprocess.CompletedProcess:
        """Generate dbt documentation.

        Returns:
            CompletedProcess with stdout/stderr.
        """
        return self._execute(self._build_command("docs", "generate"))

    def _build_command(self, *args: str) -> list[str]:
        """Build a dbt CLI command with project and profile paths.

        Args:
            args: dbt subcommand and arguments.

        Returns:
            Full command as a list of strings.
        """
        cmd = [
            "dbt",
            *args,
            "--project-dir",
            str(self.project_dir),
            "--profiles-dir",
            str(self.profiles_dir),
        ]
        return cmd

    def _execute(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Execute a dbt command and log the result.

        Args:
            cmd: Full command as a list of strings.

        Returns:
            CompletedProcess with captured stdout/stderr.
        """
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_dir),
        )

        if result.returncode == 0:
            logger.info("dbt command succeeded")
        else:
            logger.error("dbt command failed: %s", result.stderr)

        return result
