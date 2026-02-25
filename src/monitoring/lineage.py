"""Data lineage tracking for the ETL pipeline.

Records data flow between pipeline stages (source -> staging ->
intermediate -> mart) and stores lineage metadata in SQLite
for querying and visualization.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.utils.config import load_config

logger = logging.getLogger(__name__)

_DEFAULT_LINEAGE_DB = "data/lineage.db"


class LineageTracker:
    """Track and query data lineage across pipeline stages.

    Stores lineage events in a SQLite database, recording how data
    flows from sources through staging to mart tables.

    Args:
        db_path: Path to the SQLite lineage database.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            try:
                config = load_config()
                db_path = config.get("paths", {}).get("lineage_db", _DEFAULT_LINEAGE_DB)
            except FileNotFoundError:
                db_path = _DEFAULT_LINEAGE_DB

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the lineage database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lineage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    row_count INTEGER,
                    run_id TEXT,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )

    def record_event(
        self,
        source_name: str,
        source_type: str,
        target_name: str,
        target_type: str,
        row_count: int = 0,
        run_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Record a lineage event for data movement between stages.

        Args:
            source_name: Name of the data source.
            source_type: Type of source (e.g., 'csv', 'api', 'database').
            target_name: Name of the target table/model.
            target_type: Type of target (e.g., 'staging', 'intermediate', 'mart').
            row_count: Number of rows transferred.
            run_id: Optional pipeline run identifier.
            metadata: Optional extra metadata.

        Returns:
            ID of the inserted lineage event.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                INSERT INTO lineage_events
                    (source_name, source_type, target_name, target_type,
                     row_count, run_id, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_name,
                    source_type,
                    target_name,
                    target_type,
                    row_count,
                    run_id,
                    timestamp,
                    meta_json,
                ),
            )
            event_id = cursor.lastrowid

        logger.info(
            "Recorded lineage: %s (%s) -> %s (%s), %d rows",
            source_name,
            source_type,
            target_name,
            target_type,
            row_count,
        )
        return event_id

    def get_lineage(
        self,
        target_name: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query lineage events, optionally filtered by target.

        Args:
            target_name: Optional filter by target name.
            limit: Maximum number of events to return.

        Returns:
            List of lineage event dictionaries.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if target_name:
                rows = conn.execute(
                    "SELECT * FROM lineage_events WHERE target_name = ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (target_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM lineage_events ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [dict(row) for row in rows]

    def get_upstream(self, target_name: str) -> list[str]:
        """Get all upstream sources for a given target.

        Args:
            target_name: Target table/model name.

        Returns:
            List of distinct upstream source names.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT DISTINCT source_name FROM lineage_events WHERE target_name = ?",
                (target_name,),
            ).fetchall()
        return [row[0] for row in rows]

    def get_downstream(self, source_name: str) -> list[str]:
        """Get all downstream targets for a given source.

        Args:
            source_name: Source name.

        Returns:
            List of distinct downstream target names.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT DISTINCT target_name FROM lineage_events WHERE source_name = ?",
                (source_name,),
            ).fetchall()
        return [row[0] for row in rows]

    def generate_dag_text(self) -> str:
        """Generate a text-based DAG representation of data lineage.

        Returns:
            String showing the lineage flow as a text diagram.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            edges = conn.execute(
                "SELECT DISTINCT source_name, source_type, "
                "target_name, target_type FROM lineage_events"
            ).fetchall()

        if not edges:
            return "No lineage data recorded."

        lines = ["Data Lineage DAG:", "=" * 40]
        for source, stype, target, ttype in edges:
            lines.append(f"  [{stype}] {source} --> [{ttype}] {target}")

        return "\n".join(lines)
