from datetime import datetime, timedelta

from database.db import Database
from models import Metric


def test_fetch_history_returns_timestamped_values(tmp_path):
    database = Database(tmp_path / "history.duckdb")
    timestamp = datetime.now() - timedelta(minutes=1)

    database.insert_metrics([
        Metric(
            node_id="node-01",
            timestamp=timestamp,
            category="temperature",
            member_id="Die_CPU1",
            name="CPU Die 1 Temperature",
            value=42.5,
            unit="C",
        )
    ])

    history = database.fetch_history(
        "node-01", "temperature", "Die_CPU1", minutes=15
    )

    assert len(history) == 1
    assert history[0][1] == 42.5
    database.close()


def test_power_state_is_stored_as_text(tmp_path):
    database = Database(tmp_path / "power.duckdb")
    database.insert_metrics([
        Metric(
            node_id="node-01",
            timestamp=datetime.now(),
            category="power",
            member_id="PowerState",
            name="Chassis Power State",
            text_value="On",
        )
    ])

    snapshot = database.fetch_latest_snapshot()
    assert snapshot[0][5] is None
    assert snapshot[0][6] == "On"
    database.close()


def test_fresh_database_creates_schema_without_error(tmp_path):
    # Regression test: information_schema.columns must be used instead of
    # PRAGMA table_info, which raises CatalogException on a table that
    # doesn't exist yet -- i.e. on every first-ever run of the app.
    database = Database(tmp_path / "fresh.duckdb")
    columns = database._connection.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'metrics'"
    ).fetchall()
    column_map = {name: dtype.upper() for name, dtype in columns}
    assert column_map["value"] == "DOUBLE"
    assert "text_value" in column_map
    database.close()


def test_outdated_schema_is_dropped_and_recreated(tmp_path):
    # No migration framework: an old-shaped table just gets replaced.
    import duckdb

    path = tmp_path / "outdated.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("""
        CREATE TABLE metrics (
            node_id VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            category VARCHAR NOT NULL,
            member_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            value VARCHAR,
            unit VARCHAR,
            health VARCHAR,
            state VARCHAR
        )
    """)
    connection.execute(
        "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ["node-01", datetime.now(), "power", "PowerState", "Power", "On", None, "OK", "Enabled"],
    )
    connection.close()

    database = Database(path)
    columns = database._connection.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'metrics'"
    ).fetchall()
    column_map = {name: dtype.upper() for name, dtype in columns}
    assert column_map["value"] == "DOUBLE"
    assert "text_value" in column_map

    # The old row is gone -- this is a deliberate drop, not a bug.
    rows = database._connection.execute("SELECT count(*) FROM metrics").fetchone()
    assert rows[0] == 0
    database.close()
