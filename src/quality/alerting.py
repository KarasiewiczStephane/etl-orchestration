"""Alerting and failure handling for quality check results.

Routes quality check failures to configured alert channels
including structured logging and optional webhook notifications.
"""

import logging
from typing import Any, Optional

import requests

from src.quality.checks import QualityCheckResult
from src.utils.config import load_quality_rules

logger = logging.getLogger(__name__)


class AlertManager:
    """Manage alerting for quality check failures.

    Reads alert configuration from quality_rules.yaml and dispatches
    notifications to configured channels when checks fail.
    """

    def __init__(self) -> None:
        try:
            config = load_quality_rules()
            alert_config = config.get("alerts", {})
        except FileNotFoundError:
            alert_config = {}
            logger.warning("Quality rules config not found for alerting")

        self.on_failure = alert_config.get("on_failure", [])

    def process_results(
        self,
        results: list[QualityCheckResult],
        pipeline_name: str = "unknown",
    ) -> dict[str, Any]:
        """Process quality check results and trigger alerts for failures.

        Args:
            results: List of quality check results to evaluate.
            pipeline_name: Name of the pipeline that produced the results.

        Returns:
            Summary dict with pass/fail counts and alert status.
        """
        failures = [r for r in results if not r.passed]
        passed = [r for r in results if r.passed]

        summary = {
            "pipeline": pipeline_name,
            "total_checks": len(results),
            "passed": len(passed),
            "failed": len(failures),
            "critical_failures": [
                r.to_dict() for r in failures if r.severity == "critical"
            ],
            "warning_failures": [
                r.to_dict() for r in failures if r.severity == "warning"
            ],
        }

        if failures:
            self._send_alerts(failures, pipeline_name)

        return summary

    def _send_alerts(
        self,
        failures: list[QualityCheckResult],
        pipeline_name: str,
    ) -> None:
        """Dispatch alerts for failed quality checks.

        Args:
            failures: List of failed quality check results.
            pipeline_name: Name of the pipeline with failures.
        """
        for alert_config in self.on_failure:
            alert_type = alert_config.get("type")

            if alert_type == "log":
                self._alert_log(failures, pipeline_name, alert_config)
            elif alert_type == "webhook":
                if alert_config.get("enabled", True):
                    self._alert_webhook(failures, pipeline_name, alert_config)

    def _alert_log(
        self,
        failures: list[QualityCheckResult],
        pipeline_name: str,
        config: dict[str, Any],
    ) -> None:
        """Log quality check failures.

        Args:
            failures: Failed check results.
            pipeline_name: Pipeline name for context.
            config: Alert configuration.
        """
        level = config.get("level", "ERROR").upper()
        log_level = getattr(logging, level, logging.ERROR)

        for failure in failures:
            logger.log(
                log_level,
                "Quality check failed in %s: [%s] %s (severity=%s)",
                pipeline_name,
                failure.check_name,
                failure.details,
                failure.severity,
            )

    def _alert_webhook(
        self,
        failures: list[QualityCheckResult],
        pipeline_name: str,
        config: dict[str, Any],
    ) -> None:
        """Send quality check failures to a webhook endpoint.

        Args:
            failures: Failed check results.
            pipeline_name: Pipeline name for context.
            config: Alert configuration with url key.
        """
        url = config.get("url", "")
        if not url or url.startswith("${"):
            logger.debug("Webhook URL not configured, skipping")
            return

        payload = {
            "pipeline": pipeline_name,
            "failures": [f.to_dict() for f in failures],
            "failure_count": len(failures),
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Webhook alert sent to %s", url)
        except requests.RequestException as e:
            logger.error("Failed to send webhook alert: %s", e)


def handle_pipeline_failure(
    pipeline_name: str,
    error: Exception,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Handle a pipeline execution failure.

    Logs the error and returns a structured failure summary.

    Args:
        pipeline_name: Name of the failed pipeline.
        error: The exception that caused the failure.
        context: Optional additional context information.

    Returns:
        Failure summary dictionary.
    """
    logger.error(
        "Pipeline '%s' failed: %s",
        pipeline_name,
        str(error),
    )

    return {
        "pipeline": pipeline_name,
        "status": "failed",
        "error": str(error),
        "error_type": type(error).__name__,
        "context": context or {},
    }
