"""Core ETL pipeline logic for extract-validate-load workflows.

Defines reusable pipeline steps that can be called from Airflow DAGs
or executed standalone for testing and development.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from src.extractors.api_extractor import APIExtractor
from src.extractors.csv_extractor import CSVExtractor
from src.extractors.db_extractor import DatabaseExtractor
from src.loaders.duckdb_loader import DuckDBLoader
from src.utils.bookmark import BookmarkManager
from src.utils.config import load_source_config

logger = logging.getLogger(__name__)


def run_csv_pipeline(
    source_name: str = "csv_orders",
    db_path: Optional[str | Path] = None,
    bookmark_file: Optional[str] = None,
    mode: str = "append",
) -> dict[str, Any]:
    """Execute the CSV extraction pipeline.

    Args:
        source_name: Name of the source in sources.yaml.
        db_path: Override DuckDB warehouse path.
        bookmark_file: Override bookmark file path.
        mode: Load mode ('append' or 'replace').

    Returns:
        Pipeline run summary with row counts and validation status.
    """
    config = load_source_config()
    source_config = config["sources"][source_name]

    bm = BookmarkManager(bookmark_file) if bookmark_file else BookmarkManager()
    last_bookmark = bm.get_bookmark(source_name)

    extractor = CSVExtractor(source_config)
    df = extractor.extract(last_bookmark=last_bookmark)

    if df.empty:
        logger.info("No new data for %s", source_name)
        return {"source": source_name, "rows_extracted": 0, "rows_loaded": 0}

    is_valid, errors = extractor.validate_schema(df)
    if not is_valid:
        logger.error("Schema validation failed for %s: %s", source_name, errors)
        return {
            "source": source_name,
            "rows_extracted": len(df),
            "rows_loaded": 0,
            "errors": errors,
        }

    loader = DuckDBLoader(db_path=db_path)
    table_name = source_name.replace("csv_", "")
    rows_loaded = loader.load_to_staging(df, table_name, source_config["schema"], mode)

    new_bookmark = extractor.get_new_bookmark(df)
    if new_bookmark:
        bm.set_bookmark(source_name, new_bookmark)

    logger.info(
        "CSV pipeline complete: %d rows loaded for %s", rows_loaded, source_name
    )
    return {
        "source": source_name,
        "rows_extracted": len(df),
        "rows_loaded": rows_loaded,
    }


def run_api_pipeline(
    source_name: str = "api_transactions",
    db_path: Optional[str | Path] = None,
    bookmark_file: Optional[str] = None,
    mode: str = "append",
) -> dict[str, Any]:
    """Execute the API extraction pipeline.

    Args:
        source_name: Name of the source in sources.yaml.
        db_path: Override DuckDB warehouse path.
        bookmark_file: Override bookmark file path.
        mode: Load mode ('append' or 'replace').

    Returns:
        Pipeline run summary with row counts and validation status.
    """
    config = load_source_config()
    source_config = config["sources"][source_name]

    bm = BookmarkManager(bookmark_file) if bookmark_file else BookmarkManager()
    last_bookmark = bm.get_bookmark(source_name)

    extractor = APIExtractor(source_config)
    df = extractor.extract(last_bookmark=last_bookmark)

    if df.empty:
        logger.info("No new data for %s", source_name)
        return {"source": source_name, "rows_extracted": 0, "rows_loaded": 0}

    is_valid, errors = extractor.validate_schema(df)
    if not is_valid:
        logger.error("Schema validation failed for %s: %s", source_name, errors)
        return {
            "source": source_name,
            "rows_extracted": len(df),
            "rows_loaded": 0,
            "errors": errors,
        }

    loader = DuckDBLoader(db_path=db_path)
    table_name = source_name.replace("api_", "")
    rows_loaded = loader.load_to_staging(df, table_name, source_config["schema"], mode)

    new_bookmark = extractor.get_new_bookmark(df)
    if new_bookmark:
        bm.set_bookmark(source_name, new_bookmark)

    logger.info(
        "API pipeline complete: %d rows loaded for %s", rows_loaded, source_name
    )
    return {
        "source": source_name,
        "rows_extracted": len(df),
        "rows_loaded": rows_loaded,
    }


def run_db_pipeline(
    source_name: str = "db_customers",
    db_path: Optional[str | Path] = None,
    bookmark_file: Optional[str] = None,
    mode: str = "append",
) -> dict[str, Any]:
    """Execute the database extraction pipeline.

    Args:
        source_name: Name of the source in sources.yaml.
        db_path: Override DuckDB warehouse path.
        bookmark_file: Override bookmark file path.
        mode: Load mode ('append' or 'replace').

    Returns:
        Pipeline run summary with row counts and validation status.
    """
    config = load_source_config()
    source_config = config["sources"][source_name]

    bm = BookmarkManager(bookmark_file) if bookmark_file else BookmarkManager()
    last_bookmark = bm.get_bookmark(source_name)

    extractor = DatabaseExtractor(source_config)
    df = extractor.extract(last_bookmark=last_bookmark)

    if df.empty:
        logger.info("No new data for %s", source_name)
        return {"source": source_name, "rows_extracted": 0, "rows_loaded": 0}

    is_valid, errors = extractor.validate_schema(df)
    if not is_valid:
        logger.error("Schema validation failed for %s: %s", source_name, errors)
        return {
            "source": source_name,
            "rows_extracted": len(df),
            "rows_loaded": 0,
            "errors": errors,
        }

    loader = DuckDBLoader(db_path=db_path)
    table_name = source_name.replace("db_", "")
    rows_loaded = loader.load_to_staging(df, table_name, source_config["schema"], mode)

    new_bookmark = extractor.get_new_bookmark(df)
    if new_bookmark:
        bm.set_bookmark(source_name, new_bookmark)

    logger.info("DB pipeline complete: %d rows loaded for %s", rows_loaded, source_name)
    return {
        "source": source_name,
        "rows_extracted": len(df),
        "rows_loaded": rows_loaded,
    }
