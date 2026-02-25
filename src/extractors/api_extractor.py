"""REST API extractor with pagination, retry logic, and schema validation.

Fetches data from HTTP endpoints with support for paginated responses,
incremental loading via timestamp parameters, and exponential backoff
on transient failures.
"""

import logging
import time
from typing import Any, Optional

import pandas as pd
import requests

from src.utils.config import load_config

logger = logging.getLogger(__name__)


class APIExtractor:
    """Extract data from REST API endpoints with pagination support.

    Args:
        source_config: Source definition from sources.yaml containing
            base_url, endpoint, schema, pagination, and auth settings.
    """

    def __init__(self, source_config: dict[str, Any]) -> None:
        self.base_url = source_config["base_url"]
        self.endpoint = source_config["endpoint"]
        self.schema = source_config.get("schema", [])
        self.incremental = source_config.get("incremental", False)
        self.bookmark_column = source_config.get("bookmark_column")
        self.page_size = source_config.get("page_size", 100)
        self.auth_type = source_config.get("auth_type")

        try:
            config = load_config()
            api_config = config.get("api", {})
        except FileNotFoundError:
            api_config = {}

        self.timeout = api_config.get("timeout", 30)
        self.retry_attempts = api_config.get("retry_attempts", 3)
        self.retry_backoff = api_config.get("retry_backoff", 2)

    @property
    def url(self) -> str:
        """Full API endpoint URL."""
        return f"{self.base_url}{self.endpoint}"

    def extract(self, last_bookmark: Optional[str] = None) -> pd.DataFrame:
        """Extract data from the API with automatic pagination.

        Fetches all pages of data from the endpoint, optionally filtering
        for records newer than the given bookmark.

        Args:
            last_bookmark: ISO timestamp for incremental extraction.

        Returns:
            DataFrame containing all extracted records.
        """
        all_data: list[dict[str, Any]] = []
        page = 1
        has_more = True

        while has_more:
            params: dict[str, Any] = {
                "page": page,
                "page_size": self.page_size,
            }
            if self.incremental and last_bookmark:
                params["since"] = last_bookmark

            response_data = self._make_request(params)
            if response_data is None:
                logger.error("Failed to fetch page %d, stopping extraction", page)
                break

            records = response_data.get("data", [])
            all_data.extend(records)

            pagination = response_data.get("pagination", {})
            total_pages = pagination.get("pages", 1)
            has_more = page < total_pages
            page += 1

        logger.info("Extracted %d total records from %s", len(all_data), self.url)
        return pd.DataFrame(all_data)

    def _make_request(self, params: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Make an HTTP GET request with retry and exponential backoff.

        Args:
            params: Query parameters for the request.

        Returns:
            Parsed JSON response dict, or None if all retries failed.
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.get(
                    self.url,
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                wait = self.retry_backoff**attempt
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s. Retrying in %ds...",
                    self.url,
                    attempt,
                    self.retry_attempts,
                    e,
                    wait,
                )
                if attempt < self.retry_attempts:
                    time.sleep(wait)

        logger.error("All %d attempts failed for %s", self.retry_attempts, self.url)
        return None

    def validate_schema(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Validate API response data against the expected schema.

        Args:
            df: DataFrame to validate.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: list[str] = []

        if df.empty:
            return True, errors

        expected_columns = {col["name"] for col in self.schema}
        actual_columns = set(df.columns)

        missing = expected_columns - actual_columns
        if missing:
            errors.append(f"Missing columns: {sorted(missing)}")

        for col_def in self.schema:
            col_name = col_def["name"]
            if col_name not in df.columns:
                continue

            if not col_def.get("nullable", True):
                null_count = df[col_name].isna().sum()
                if null_count > 0:
                    errors.append(
                        f"Column '{col_name}' has {null_count} null values "
                        f"but is non-nullable"
                    )

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("API schema validation passed")
        else:
            logger.warning("API schema validation failed with %d errors", len(errors))

        return is_valid, errors

    def get_new_bookmark(self, df: pd.DataFrame) -> Optional[str]:
        """Get the latest bookmark value from extracted data.

        Args:
            df: Extracted DataFrame.

        Returns:
            String representation of the max bookmark column value,
            or None if not applicable.
        """
        if df.empty:
            return None
        if self.bookmark_column and self.bookmark_column in df.columns:
            return str(df[self.bookmark_column].max())
        return None
