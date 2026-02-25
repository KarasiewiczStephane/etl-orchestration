"""Bookmark manager for tracking incremental loading state.

Persists bookmark values (e.g., last loaded timestamp) per source
so that incremental extractions can resume from where they left off.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_BOOKMARK_FILE = "data/bookmarks.json"


class BookmarkManager:
    """Manage bookmark state for incremental source loading.

    Stores and retrieves bookmark values in a JSON file, allowing
    each source to track its extraction progress independently.

    Args:
        bookmark_file: Path to the JSON file for bookmark persistence.
    """

    def __init__(self, bookmark_file: str = _DEFAULT_BOOKMARK_FILE) -> None:
        self.bookmark_file = Path(bookmark_file)
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create the bookmark file and parent directories if missing."""
        if not self.bookmark_file.exists():
            self.bookmark_file.parent.mkdir(parents=True, exist_ok=True)
            self.bookmark_file.write_text("{}")
            logger.info("Created bookmark file at %s", self.bookmark_file)

    def get_bookmark(self, source_name: str) -> Optional[str]:
        """Retrieve the last bookmark value for a source.

        Args:
            source_name: Identifier for the data source.

        Returns:
            The stored bookmark value, or None if not set.
        """
        bookmarks = json.loads(self.bookmark_file.read_text())
        return bookmarks.get(source_name)

    def set_bookmark(self, source_name: str, value: str) -> None:
        """Store a bookmark value for a source.

        Args:
            source_name: Identifier for the data source.
            value: Bookmark value to persist.
        """
        bookmarks = json.loads(self.bookmark_file.read_text())
        bookmarks[source_name] = value
        self.bookmark_file.write_text(json.dumps(bookmarks, indent=2))
        logger.info("Updated bookmark for '%s': %s", source_name, value)

    def clear_bookmark(self, source_name: str) -> None:
        """Remove a bookmark for a source.

        Args:
            source_name: Identifier for the data source.
        """
        bookmarks = json.loads(self.bookmark_file.read_text())
        if source_name in bookmarks:
            del bookmarks[source_name]
            self.bookmark_file.write_text(json.dumps(bookmarks, indent=2))
            logger.info("Cleared bookmark for '%s'", source_name)

    def list_bookmarks(self) -> dict[str, str]:
        """Return all stored bookmarks.

        Returns:
            Dictionary mapping source names to bookmark values.
        """
        return json.loads(self.bookmark_file.read_text())
