import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

from models import Metric


LOGGER = logging.getLogger("clustermon.database")

SCHEMA = '''
CREATE TABLE IF NOT EXISTS metrics (
    node_id VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    category VARCHAR NOT NULL,
    member_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    value DOUBLE,
    text_value VARCHAR,
    unit VARCHAR,
    health VARCHAR,
    state VARCHAR
);
'''


class Database:
    def __init__(self, path="cluster_mon.duckdb"):
        self.path = str(Path(path))
        self._connection = duckdb.connect(self.path)
        self._ensure_schema()

    def _ensure_schema(self):
        # information_schema never raises for a table that doesn't exist yet,
        # unlike PRAGMA table_info -- that distinction is the whole fix.
        columns = self._connection.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'metrics'"
        ).fetchall()

        if not columns:
            self._connection.execute(SCHEMA)
            return

        column_map = {name: dtype.upper() for name, dtype in columns}
        if column_map.get("value") != "DOUBLE" or "text_value" not in column_map:
            # No migration framework: nothing currently in front of a real
            # BMC predates this schema, so there's no history to preserve.
            LOGGER.warning("metrics table has an outdated schema in %s; recreating it", self.path)
            self._connection.execute("DROP TABLE metrics")
            self._connection.execute(SCHEMA)

    def insert_metrics(self, metrics):
        rows = [
            (
                metric.node_id,
                metric.timestamp,
                metric.category,
                metric.member_id,
                metric.name,
                metric.value,
                metric.text_value,
                metric.unit,
                metric.health,
                metric.state,
            )
            for metric in metrics
        ]

        if not rows:
            return

        self._connection.executemany(
            '''
            INSERT INTO metrics (
                node_id, timestamp, category, member_id, name,
                value, text_value, unit, health, state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            rows,
        )

    def fetch_latest_snapshot(self):
        return self._connection.execute(
            '''
            SELECT
                node_id, timestamp, category, member_id, name,
                value, text_value, unit, health, state
            FROM metrics
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY node_id, category, member_id
                ORDER BY timestamp DESC
            ) = 1
            ORDER BY node_id, category, member_id
            '''
        ).fetchall()

    def fetch_history(self, node_id, category, member_id, minutes=15):
        """Return timestamp/value pairs for one numeric metric."""
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            minutes=minutes
        )

        return self._connection.execute(
            '''
            SELECT timestamp, value
            FROM metrics
            WHERE node_id = ?
              AND category = ?
              AND member_id = ?
              AND timestamp >= ?
              AND value IS NOT NULL
            ORDER BY timestamp ASC
            ''',
            [node_id, category, member_id, since],
        ).fetchall()

    def close(self):
        self._connection.close()
