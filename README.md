# ClusterMON v0.3

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
- Terminal-native CPU temperature and fan-speed graphs
- Selectable node telemetry history
- Fifteen-minute graph window
- Five-second refresh
- Debug logging
- Configuration validation
- Offline/unit tests for component parsing

## v0.3 changes

- Numeric telemetry is stored as DuckDB `DOUBLE` values.
- Text telemetry such as `On`/`Off` is stored separately in `text_value`.
- Existing v0.1/v0.2 databases are migrated automatically without discarding history.
- One persistent HTTP/Redfish client is reused per BMC instead of creating a new TLS/client session every poll.
- BMC discovery asks for confirmation before scanning all detected local subnets; use `--yes` for unattended operation.
- Discovery no longer carries a dead node-ID mode parameter.

## Automatic BMC discovery

ClusterMON includes a bootstrap tool for discovering Redfish BMCs on the local network. It detects valid Redfish endpoints and writes `config.json`. A scan of all connected /24-or-smaller IPv4 networks requires confirmation.

```bash
python tools/discover_bmcs.py
```

For unattended use after reviewing the detected networks:

```bash
python tools/discover_bmcs.py --yes
```

For a specific subnet:

```bash
python tools/discover_bmcs.py --network 172.16.1.0/24
```

Passwords are never written to `config.json`. Set the shared BMC password in the current shell with:

```bash
eval "$(python tools/discover_bmcs.py --export-password)"
```

The generated configuration uses `CLUSTERMON_BMC_PASSWORD` for the discovered nodes.

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

## Terminal-first by design

ClusterMON is intentionally a terminal application. It does not require a web
browser, web server, Prometheus, Grafana, Kubernetes, or another monitoring
stack. The TUI provides both the operational dashboard and historical graphs.

The goal is to run ClusterMON locally or over SSH and see useful node telemetry
without leaving the terminal.

## v0.2 graphs

Select a node in the main table to view the last 15 minutes of:

- CPU Die 1 temperature
- CPU Die 2 temperature
- Average fan RPM

Graphs are rendered directly in the terminal and use the existing DuckDB metric
history. No additional plotting service is required.

v0.3 still intentionally does not include Prometheus/Grafana, Redfish event
subscriptions, GPU/storage/memory monitoring, or alert rules.
