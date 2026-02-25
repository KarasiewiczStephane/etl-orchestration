"""Tests for configuration loading utilities."""

from pathlib import Path

import pytest

from src.utils.config import (
    get_project_root,
    load_config,
    load_quality_rules,
    load_source_config,
    load_yaml,
)


class TestLoadYaml:
    """Tests for the load_yaml function."""

    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        """Valid YAML file is loaded correctly."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("key: value\nnested:\n  a: 1\n")

        result = load_yaml(str(config_file))

        assert result == {"key": "value", "nested": {"a": 1}}

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised for nonexistent file."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_yaml(str(tmp_path / "missing.yaml"))

    def test_handles_empty_yaml(self, tmp_path: Path) -> None:
        """Empty YAML file returns None."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        result = load_yaml(str(config_file))

        assert result is None

    def test_loads_list_yaml(self, tmp_path: Path) -> None:
        """YAML file with list structure loads correctly."""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n")

        result = load_yaml(str(config_file))

        assert result == ["item1", "item2"]


class TestLoadConfig:
    """Tests for project configuration loaders."""

    def test_load_config_returns_dict(self) -> None:
        """Main config loads as a dictionary."""
        config = load_config()
        assert isinstance(config, dict)
        assert "project" in config
        assert "warehouse" in config

    def test_load_source_config_returns_dict(self) -> None:
        """Source config loads as a dictionary."""
        config = load_source_config()
        assert isinstance(config, dict)
        assert "sources" in config

    def test_load_quality_rules_returns_dict(self) -> None:
        """Quality rules config loads as a dictionary."""
        config = load_quality_rules()
        assert isinstance(config, dict)
        assert "quality_rules" in config

    def test_source_config_has_expected_sources(self) -> None:
        """Source config contains all defined sources."""
        config = load_source_config()
        sources = config["sources"]
        assert "csv_orders" in sources
        assert "api_transactions" in sources
        assert "db_customers" in sources

    def test_source_schema_has_required_fields(self) -> None:
        """Each source schema entry has name and type."""
        config = load_source_config()
        for source_name, source in config["sources"].items():
            assert "schema" in source, f"{source_name} missing schema"
            for field in source["schema"]:
                assert "name" in field
                assert "type" in field


class TestGetProjectRoot:
    """Tests for project root resolution."""

    def test_returns_path(self) -> None:
        """Project root is a valid Path object."""
        root = get_project_root()
        assert isinstance(root, Path)

    def test_root_contains_configs(self) -> None:
        """Project root contains the configs directory."""
        root = get_project_root()
        assert (root / "configs").exists()
