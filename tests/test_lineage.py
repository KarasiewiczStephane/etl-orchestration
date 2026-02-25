"""Tests for the lineage tracking module."""

from pathlib import Path

import pytest

from src.monitoring.lineage import LineageTracker


@pytest.fixture()
def tracker(tmp_path: Path) -> LineageTracker:
    """Create a LineageTracker with temp database."""
    return LineageTracker(db_path=tmp_path / "lineage.db")


class TestLineageTrackerRecordEvent:
    """Tests for recording lineage events."""

    def test_record_returns_id(self, tracker: LineageTracker) -> None:
        """Recording returns a positive event ID."""
        event_id = tracker.record_event(
            "csv_orders", "csv", "staging.orders", "staging", row_count=100
        )
        assert event_id > 0

    def test_record_with_metadata(self, tracker: LineageTracker) -> None:
        """Metadata is stored with the event."""
        tracker.record_event(
            "csv_orders",
            "csv",
            "staging.orders",
            "staging",
            metadata={"quality_check": "passed"},
        )
        events = tracker.get_lineage()
        assert len(events) == 1
        assert events[0]["metadata"] is not None

    def test_record_with_run_id(self, tracker: LineageTracker) -> None:
        """Run ID is stored with the event."""
        tracker.record_event(
            "csv_orders",
            "csv",
            "staging.orders",
            "staging",
            run_id="run_001",
        )
        events = tracker.get_lineage()
        assert events[0]["run_id"] == "run_001"


class TestLineageTrackerQuery:
    """Tests for querying lineage events."""

    def test_get_all_lineage(self, tracker: LineageTracker) -> None:
        """All events are returned without filter."""
        tracker.record_event("a", "csv", "b", "staging")
        tracker.record_event("b", "staging", "c", "mart")
        events = tracker.get_lineage()
        assert len(events) == 2

    def test_get_lineage_by_target(self, tracker: LineageTracker) -> None:
        """Events filtered by target name."""
        tracker.record_event("a", "csv", "staging.orders", "staging")
        tracker.record_event("b", "api", "staging.transactions", "staging")
        events = tracker.get_lineage(target_name="staging.orders")
        assert len(events) == 1
        assert events[0]["source_name"] == "a"

    def test_get_lineage_respects_limit(self, tracker: LineageTracker) -> None:
        """Limit parameter constrains results."""
        for i in range(10):
            tracker.record_event(f"src_{i}", "csv", "target", "staging")
        events = tracker.get_lineage(limit=3)
        assert len(events) == 3

    def test_empty_lineage(self, tracker: LineageTracker) -> None:
        """Empty database returns empty list."""
        events = tracker.get_lineage()
        assert events == []


class TestLineageTrackerUpstreamDownstream:
    """Tests for upstream and downstream queries."""

    def test_get_upstream(self, tracker: LineageTracker) -> None:
        """Upstream sources for a target are returned."""
        tracker.record_event("csv_orders", "csv", "staging.orders", "staging")
        tracker.record_event("api_orders", "api", "staging.orders", "staging")
        upstream = tracker.get_upstream("staging.orders")
        assert set(upstream) == {"csv_orders", "api_orders"}

    def test_get_downstream(self, tracker: LineageTracker) -> None:
        """Downstream targets for a source are returned."""
        tracker.record_event("staging.orders", "staging", "mart.summary", "mart")
        tracker.record_event("staging.orders", "staging", "mart.daily", "mart")
        downstream = tracker.get_downstream("staging.orders")
        assert set(downstream) == {"mart.summary", "mart.daily"}

    def test_empty_upstream(self, tracker: LineageTracker) -> None:
        """No upstream for unknown target."""
        assert tracker.get_upstream("nonexistent") == []

    def test_empty_downstream(self, tracker: LineageTracker) -> None:
        """No downstream for unknown source."""
        assert tracker.get_downstream("nonexistent") == []


class TestLineageTrackerVisualization:
    """Tests for lineage visualization."""

    def test_generate_dag_text(self, tracker: LineageTracker) -> None:
        """DAG text contains lineage edges."""
        tracker.record_event("csv_orders", "csv", "staging.orders", "staging")
        tracker.record_event("staging.orders", "staging", "mart.summary", "mart")
        text = tracker.generate_dag_text()
        assert "csv_orders" in text
        assert "staging.orders" in text
        assert "mart.summary" in text
        assert "-->" in text

    def test_empty_dag_text(self, tracker: LineageTracker) -> None:
        """Empty lineage produces informative message."""
        text = tracker.generate_dag_text()
        assert "No lineage data" in text
