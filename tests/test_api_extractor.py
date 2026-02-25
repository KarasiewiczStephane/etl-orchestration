"""Tests for the REST API extractor module."""

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.extractors.api_extractor import APIExtractor


@pytest.fixture()
def api_config() -> dict[str, Any]:
    """Build an API source config for testing."""
    return {
        "base_url": "http://localhost:5000",
        "endpoint": "/api/transactions",
        "schema": [
            {"name": "transaction_id", "type": "INTEGER", "nullable": False},
            {"name": "customer_id", "type": "INTEGER", "nullable": False},
            {"name": "amount", "type": "DOUBLE", "nullable": False},
            {"name": "transaction_date", "type": "TIMESTAMP", "nullable": False},
            {"name": "category", "type": "VARCHAR", "nullable": False},
        ],
        "incremental": True,
        "bookmark_column": "transaction_date",
        "page_size": 2,
    }


def _mock_response(data: list, page: int, total: int, page_size: int) -> MagicMock:
    """Build a mock requests.Response with pagination metadata."""
    mock = MagicMock()
    mock.status_code = 200
    pages = (total + page_size - 1) // page_size
    mock.json.return_value = {
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": pages,
        },
    }
    mock.raise_for_status.return_value = None
    return mock


class TestAPIExtractorExtract:
    """Tests for the extract method."""

    @patch("src.extractors.api_extractor.requests.get")
    def test_single_page_extraction(
        self, mock_get: MagicMock, api_config: dict
    ) -> None:
        """Single-page response is extracted correctly."""
        records = [
            {"transaction_id": 1, "customer_id": 10, "amount": 50.0},
            {"transaction_id": 2, "customer_id": 20, "amount": 75.0},
        ]
        mock_get.return_value = _mock_response(records, 1, 2, 2)

        extractor = APIExtractor(api_config)
        df = extractor.extract()

        assert len(df) == 2
        assert "transaction_id" in df.columns

    @patch("src.extractors.api_extractor.requests.get")
    def test_multi_page_extraction(self, mock_get: MagicMock, api_config: dict) -> None:
        """Multiple pages are fetched and concatenated."""
        page1 = [{"id": 1}, {"id": 2}]
        page2 = [{"id": 3}]

        mock_get.side_effect = [
            _mock_response(page1, 1, 3, 2),
            _mock_response(page2, 2, 3, 2),
        ]

        extractor = APIExtractor(api_config)
        df = extractor.extract()

        assert len(df) == 3

    @patch("src.extractors.api_extractor.requests.get")
    def test_incremental_sends_since_param(
        self, mock_get: MagicMock, api_config: dict
    ) -> None:
        """Incremental extraction sends 'since' parameter."""
        mock_get.return_value = _mock_response([], 1, 0, 2)

        extractor = APIExtractor(api_config)
        extractor.extract(last_bookmark="2024-06-01T00:00:00")

        call_params = mock_get.call_args[1]["params"]
        assert call_params["since"] == "2024-06-01T00:00:00"

    @patch("src.extractors.api_extractor.requests.get")
    def test_empty_response(self, mock_get: MagicMock, api_config: dict) -> None:
        """Empty API response returns empty DataFrame."""
        mock_get.return_value = _mock_response([], 1, 0, 2)

        extractor = APIExtractor(api_config)
        df = extractor.extract()

        assert df.empty


class TestAPIExtractorRetry:
    """Tests for retry logic."""

    @patch("src.extractors.api_extractor.time.sleep")
    @patch("src.extractors.api_extractor.requests.get")
    def test_retries_on_failure(
        self, mock_get: MagicMock, mock_sleep: MagicMock, api_config: dict
    ) -> None:
        """Request is retried on transient failures."""
        import requests as req

        mock_get.side_effect = [
            req.ConnectionError("Connection refused"),
            _mock_response([{"id": 1}], 1, 1, 2),
        ]

        extractor = APIExtractor(api_config)
        df = extractor.extract()

        assert len(df) == 1
        assert mock_get.call_count == 2

    @patch("src.extractors.api_extractor.time.sleep")
    @patch("src.extractors.api_extractor.requests.get")
    def test_returns_empty_after_max_retries(
        self, mock_get: MagicMock, mock_sleep: MagicMock, api_config: dict
    ) -> None:
        """Returns empty DataFrame when all retries exhausted."""
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        extractor = APIExtractor(api_config)
        df = extractor.extract()

        assert df.empty


class TestAPIExtractorValidateSchema:
    """Tests for schema validation."""

    def test_valid_data_passes(self, api_config: dict) -> None:
        """Valid data passes schema validation."""
        extractor = APIExtractor(api_config)
        df = pd.DataFrame(
            {
                "transaction_id": [1],
                "customer_id": [10],
                "amount": [50.0],
                "transaction_date": ["2024-01-01"],
                "category": ["electronics"],
            }
        )
        is_valid, errors = extractor.validate_schema(df)
        assert is_valid
        assert errors == []

    def test_missing_columns_detected(self, api_config: dict) -> None:
        """Missing columns produce validation errors."""
        extractor = APIExtractor(api_config)
        df = pd.DataFrame({"transaction_id": [1]})
        is_valid, errors = extractor.validate_schema(df)
        assert not is_valid
        assert any("Missing columns" in e for e in errors)

    def test_empty_dataframe_is_valid(self, api_config: dict) -> None:
        """Empty DataFrame passes validation."""
        extractor = APIExtractor(api_config)
        is_valid, errors = extractor.validate_schema(pd.DataFrame())
        assert is_valid


class TestAPIExtractorBookmark:
    """Tests for bookmark tracking."""

    def test_get_bookmark(self, api_config: dict) -> None:
        """Bookmark returns max value of bookmark column."""
        extractor = APIExtractor(api_config)
        df = pd.DataFrame(
            {"transaction_date": ["2024-01-01", "2024-06-15", "2024-03-10"]}
        )
        bookmark = extractor.get_new_bookmark(df)
        assert bookmark == "2024-06-15"

    def test_get_bookmark_empty(self, api_config: dict) -> None:
        """Empty DataFrame returns None."""
        extractor = APIExtractor(api_config)
        assert extractor.get_new_bookmark(pd.DataFrame()) is None
