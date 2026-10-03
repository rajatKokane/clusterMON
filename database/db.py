from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

from models import Metric


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
        columns = self._connection.execute(
            "PRAGMA table_info('metrics')"
        ).fetchall()

        if not columns:
            self._connection.execute(SCHEMA)
            return

        column_map = {row[1]: str(row[2]).upper() for row in columns}
        if column_map.get("value") != "DOUBLE" or "text_value" not in column_map:
            self._migrate_v02_schema(column_map)

    def _migrate_v02_schema(self, column_map):
        """Migrate the v0.1/v0.2 string value column without losing history."""
        self._connection.execute("BEGIN TRANSACTION")
        try:
            self._connection.execute("DROP TABLE IF EXISTS metrics_v03")
            self._connection.execute(
                '''
                CREATE TABLE metrics_v03 (
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
                )
                '''
            )

            legacy_value = "value" if "value" in column_map else "NULL"
            legacy_text = "text_value" if "text_value" in column_map else "NULL"

            self._connection.execute(
                f'''
                INSERT INTO metrics_v03 (
                    node_id, timestamp, category, member_id, name,
                    value, text_value, unit, health, state
                )
                SELECT
                    node_id,
                    timestamp,
                    category,
                    member_id,
                    name,
                    TRY_CAST({legacy_value} AS DOUBLE),
                    CASE
                        WHEN TRY_CAST({legacy_value} AS DOUBLE) IS NULL
                        THEN {legacy_text}
                        ELSE NULL
                    END,
                    unit,
                    health,
                    state
                FROM metrics
                '''
            )
            self._connection.execute("DROP TABLE metrics")
            self._connection.execute("ALTER TABLE metrics_v03 RENAME TO metrics")
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

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
