"""Tests for the bookmark manager module."""

from pathlib import Path

from src.utils.bookmark import BookmarkManager


class TestBookmarkManager:
    """Tests for BookmarkManager persistence operations."""

    def test_creates_file_on_init(self, tmp_path: Path) -> None:
        """Bookmark file is created if it doesn't exist."""
        BookmarkManager(str(tmp_path / "bookmarks.json"))
        assert (tmp_path / "bookmarks.json").exists()

    def test_set_and_get_bookmark(self, tmp_path: Path) -> None:
        """Stored bookmark can be retrieved."""
        bm = BookmarkManager(str(tmp_path / "bookmarks.json"))
        bm.set_bookmark("source_a", "2024-01-01")
        assert bm.get_bookmark("source_a") == "2024-01-01"

    def test_get_missing_bookmark_returns_none(self, tmp_path: Path) -> None:
        """Missing source returns None."""
        bm = BookmarkManager(str(tmp_path / "bookmarks.json"))
        assert bm.get_bookmark("nonexistent") is None

    def test_update_existing_bookmark(self, tmp_path: Path) -> None:
        """Updating a bookmark overwrites the previous value."""
        bm = BookmarkManager(str(tmp_path / "bookmarks.json"))
        bm.set_bookmark("source_a", "2024-01-01")
        bm.set_bookmark("source_a", "2024-06-01")
        assert bm.get_bookmark("source_a") == "2024-06-01"

    def test_clear_bookmark(self, tmp_path: Path) -> None:
        """Cleared bookmark returns None on next get."""
        bm = BookmarkManager(str(tmp_path / "bookmarks.json"))
        bm.set_bookmark("source_a", "2024-01-01")
        bm.clear_bookmark("source_a")
        assert bm.get_bookmark("source_a") is None

    def test_clear_missing_bookmark_no_error(self, tmp_path: Path) -> None:
        """Clearing a nonexistent bookmark does not raise."""
        bm = BookmarkManager(str(tmp_path / "bookmarks.json"))
        bm.clear_bookmark("nonexistent")

    def test_list_bookmarks(self, tmp_path: Path) -> None:
        """All bookmarks are returned as a dictionary."""
        bm = BookmarkManager(str(tmp_path / "bookmarks.json"))
        bm.set_bookmark("a", "val_a")
        bm.set_bookmark("b", "val_b")
        result = bm.list_bookmarks()
        assert result == {"a": "val_a", "b": "val_b"}

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        """Bookmarks persist between manager instances."""
        path = str(tmp_path / "bookmarks.json")
        bm1 = BookmarkManager(path)
        bm1.set_bookmark("src", "2024-03-01")

        bm2 = BookmarkManager(path)
        assert bm2.get_bookmark("src") == "2024-03-01"

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Parent directories are created for the bookmark file."""
        bm = BookmarkManager(str(tmp_path / "nested" / "dir" / "bookmarks.json"))
        bm.set_bookmark("test", "value")
        assert bm.get_bookmark("test") == "value"
