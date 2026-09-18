# ClusterMON v0.1

A minimal, open-source Redfish-based HPC node monitoring TUI.

## v0.1

- Multiple BMCs
- Concurrent async polling
- Host power state
- CPU die temperatures
- Average fan RPM
- Reported chassis health
- Per-node collection status
- DuckDB metric history
- Five-second refresh
- Debug logging
- Configuration validation
- Offline/unit tests for component parsing

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json
export CLUSTERMON_TEST_SERVER_01_PASSWORD='your-password'

python app.py
```

Debug mode:

```bash
python app.py --debug
```

Custom configuration/database paths:

```bash
python app.py --config my-cluster.json --database data/cluster.duckdb
```

## Adding nodes

Edit only `config.json`.

Example:

```json
{
    "nodes": [
        {
            "node_id": "test-server-01",
            "bmc_url": "https://172.16.1.16",
            "username": "root",
            "password_env": "CLUSTERMON_TEST_SERVER_01_PASSWORD",
            "verify_ssl": false
        },
        {
            "node_id": "test-server-02",
            "bmc_url": "https://172.16.1.17",
            "username": "root",
            "password_env": "CLUSTERMON_TEST_SERVER_02_PASSWORD",
            "verify_ssl": false
        }
    ]
}
```

No Python changes are needed to add a node.

## Adding components

See `CONTRIBUTING.md`.

The intended path is:

1. Add Redfish parsing in `redfish/components.py`.
2. Return `Metric` objects.
3. Register the collector in `redfish/collector.py`.
4. Add a `DashboardColumn` in `ui/dashboard.py` if it belongs on the main TUI.

The generic database schema means new metrics normally do not require schema
changes.

## Project layout

```text
cluster-mon/
├── app.py
├── config.py
├── config.example.json
├── models.py
├── requirements.txt
├── README.md
├── CONTRIBUTING.md
├── redfish/
│   ├── client.py
│   ├── collector.py
│   └── components.py
├── database/
│   └── db.py
├── ui/
│   └── dashboard.py
└── tests/
    ├── test_components.py
    └── test_config.py
```

v0.1 intentionally does not include Prometheus/Grafana, Redfish event
subscriptions, GPU/storage/memory monitoring, alert rules, graphs, or
automatic discovery.
