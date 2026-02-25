"""Tests for the Flask mock API server."""

import pytest

from mock_api.app import app


@pytest.fixture()
def client():
    """Create a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestMockAPITransactions:
    """Tests for the /api/transactions endpoint."""

    def test_returns_200(self, client) -> None:
        """Transaction endpoint returns 200."""
        response = client.get("/api/transactions")
        assert response.status_code == 200

    def test_returns_paginated_data(self, client) -> None:
        """Response contains data and pagination keys."""
        response = client.get("/api/transactions")
        data = response.get_json()
        assert "data" in data
        assert "pagination" in data

    def test_page_size_parameter(self, client) -> None:
        """Page size limits number of returned records."""
        response = client.get("/api/transactions?page_size=5")
        data = response.get_json()
        assert len(data["data"]) == 5

    def test_pagination_metadata(self, client) -> None:
        """Pagination metadata is correct."""
        response = client.get("/api/transactions?page=1&page_size=10")
        pagination = response.get_json()["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 10
        assert pagination["total"] > 0

    def test_since_filter(self, client) -> None:
        """Since parameter filters transactions."""
        response_all = client.get("/api/transactions?page_size=500")
        total_all = len(response_all.get_json()["data"])

        response_filtered = client.get(
            "/api/transactions?since=2024-07-01T00:00:00&page_size=500"
        )
        total_filtered = len(response_filtered.get_json()["data"])

        assert total_filtered <= total_all

    def test_deterministic_data(self, client) -> None:
        """Two requests return identical data (seeded RNG)."""
        r1 = client.get("/api/transactions?page_size=5")
        r2 = client.get("/api/transactions?page_size=5")
        assert r1.get_json()["data"] == r2.get_json()["data"]


class TestMockAPIHealth:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client) -> None:
        """Health endpoint returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_status(self, client) -> None:
        """Health response contains status field."""
        data = client.get("/api/health").get_json()
        assert data["status"] == "healthy"
