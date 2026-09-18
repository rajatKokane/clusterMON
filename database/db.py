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
    value VARCHAR,
    unit VARCHAR,
    health VARCHAR,
    state VARCHAR
);
'''


class Database:
    def __init__(self, path="cluster_mon.duckdb"):
        self.path = str(Path(path))
        self._connection = duckdb.connect(self.path)
        self._connection.execute(SCHEMA)

    def insert_metrics(self, metrics):
        rows = [
            (
                metric.node_id,
                metric.timestamp,
                metric.category,
                metric.member_id,
                metric.name,
                None if metric.value is None else str(metric.value),
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
                value, unit, health, state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            rows,
        )

    def fetch_latest_snapshot(self):
        return self._connection.execute(
            '''
            SELECT
                node_id, timestamp, category, member_id, name,
                value, unit, health, state
            FROM metrics
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY node_id, category, member_id
                ORDER BY timestamp DESC
            ) = 1
            ORDER BY node_id, category, member_id
            '''
        ).fetchall()

    def close(self):
        self._connection.close()
