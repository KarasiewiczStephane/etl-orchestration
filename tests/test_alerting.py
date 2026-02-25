"""Tests for the alerting and failure handling module."""

from unittest.mock import MagicMock, patch

import pytest

from src.quality.alerting import AlertManager, handle_pipeline_failure
from src.quality.checks import QualityCheckResult


@pytest.fixture()
def alert_manager() -> AlertManager:
    """Create an AlertManager instance."""
    return AlertManager()


@pytest.fixture()
def failed_results() -> list[QualityCheckResult]:
    """Create a list of failed quality check results."""
    return [
        QualityCheckResult(
            "schema_validation",
            passed=False,
            severity="critical",
            details="Missing columns: ['col_a']",
        ),
        QualityCheckResult(
            "row_count_check",
            passed=False,
            severity="warning",
            details="Row count: 0, minimum: 1",
        ),
    ]


@pytest.fixture()
def passing_results() -> list[QualityCheckResult]:
    """Create a list of passing quality check results."""
    return [
        QualityCheckResult("schema_validation", passed=True, severity="critical"),
        QualityCheckResult("row_count_check", passed=True, severity="warning"),
    ]


class TestAlertManagerProcessResults:
    """Tests for result processing."""

    def test_all_passing_no_alerts(
        self, alert_manager: AlertManager, passing_results: list
    ) -> None:
        """No alerts triggered when all checks pass."""
        summary = alert_manager.process_results(passing_results, "test_pipeline")
        assert summary["failed"] == 0
        assert summary["passed"] == 2

    def test_failures_counted(
        self, alert_manager: AlertManager, failed_results: list
    ) -> None:
        """Failures are counted correctly."""
        summary = alert_manager.process_results(failed_results, "test_pipeline")
        assert summary["failed"] == 2
        assert len(summary["critical_failures"]) == 1
        assert len(summary["warning_failures"]) == 1

    def test_summary_contains_pipeline_name(
        self, alert_manager: AlertManager, passing_results: list
    ) -> None:
        """Summary includes the pipeline name."""
        summary = alert_manager.process_results(passing_results, "my_pipeline")
        assert summary["pipeline"] == "my_pipeline"

    def test_mixed_results(self, alert_manager: AlertManager) -> None:
        """Mixed pass/fail results are tracked correctly."""
        results = [
            QualityCheckResult("check_a", passed=True),
            QualityCheckResult("check_b", passed=False, details="failed"),
        ]
        summary = alert_manager.process_results(results, "test")
        assert summary["passed"] == 1
        assert summary["failed"] == 1


class TestAlertManagerLogAlerts:
    """Tests for log-based alerting."""

    def test_failures_logged(
        self, alert_manager: AlertManager, failed_results: list
    ) -> None:
        """Failed checks are logged."""
        with patch("src.quality.alerting.logger") as mock_logger:
            alert_manager._alert_log(failed_results, "test", {"level": "ERROR"})
            assert mock_logger.log.call_count == 2


class TestAlertManagerWebhook:
    """Tests for webhook alerting."""

    @patch("src.quality.alerting.requests.post")
    def test_webhook_called(
        self,
        mock_post: MagicMock,
        alert_manager: AlertManager,
        failed_results: list,
    ) -> None:
        """Webhook is called with failure data."""
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        alert_manager._alert_webhook(
            failed_results, "test", {"url": "https://hooks.example.com/test"}
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["failure_count"] == 2

    def test_webhook_skipped_if_url_not_configured(
        self,
        alert_manager: AlertManager,
        failed_results: list,
    ) -> None:
        """Webhook is skipped when URL is a placeholder."""
        with patch("src.quality.alerting.requests.post") as mock_post:
            alert_manager._alert_webhook(
                failed_results, "test", {"url": "${ALERT_WEBHOOK_URL}"}
            )
            mock_post.assert_not_called()

    @patch("src.quality.alerting.requests.post")
    def test_webhook_error_handled(
        self,
        mock_post: MagicMock,
        alert_manager: AlertManager,
        failed_results: list,
    ) -> None:
        """Webhook errors are caught and logged."""
        import requests as req

        mock_post.side_effect = req.ConnectionError("refused")

        alert_manager._alert_webhook(
            failed_results, "test", {"url": "https://hooks.example.com/test"}
        )


class TestHandlePipelineFailure:
    """Tests for pipeline failure handling."""

    def test_returns_failure_summary(self) -> None:
        """Returns structured failure information."""
        error = ValueError("Data corrupt")
        result = handle_pipeline_failure("csv_pipeline", error)
        assert result["status"] == "failed"
        assert result["error"] == "Data corrupt"
        assert result["error_type"] == "ValueError"
        assert result["pipeline"] == "csv_pipeline"

    def test_includes_context(self) -> None:
        """Context is included in failure summary."""
        error = RuntimeError("timeout")
        ctx = {"source": "orders", "attempt": 3}
        result = handle_pipeline_failure("api_pipeline", error, context=ctx)
        assert result["context"]["source"] == "orders"

    def test_default_empty_context(self) -> None:
        """Default context is empty dict."""
        result = handle_pipeline_failure("test", Exception("err"))
        assert result["context"] == {}
