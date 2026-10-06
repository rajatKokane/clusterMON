# Contributing to ClusterMON

ClusterMON is intentionally designed around simple extension points.

## Add a node

No Python changes are required.

1. Copy a node entry in `config.json`.
2. Give it a unique `node_id`.
3. Set its BMC URL.
4. Set `password_env` to the name of an environment variable.
5. Export that password.

Example:

```json
{
    "node_id": "test-server-02",
    "bmc_url": "https://172.16.1.17",
    "username": "root",
    "password_env": "CLUSTERMON_TEST_SERVER_02_PASSWORD",
    "verify_ssl": false
}
```

```bash
export CLUSTERMON_TEST_SERVER_02_PASSWORD='your-password'
python app.py
```

## Add a monitored component

1. Add a collector in `redfish/components.py`.
2. Return `Metric` objects.
3. Call it from `RedfishCollector.collect()`.

Example:

```python
def collect_memory(node_id, resource, timestamp):
    return [
        Metric(
            node_id,
            timestamp,
            "memory",
            "TotalMemory",
            "Total Memory",
            value=512,
            unit="GiB",
            health="OK",
            state="Enabled",
        )
    ]
```

Always pass `value`, `text_value`, `unit`, `health`, and `state` as keyword
arguments. They're easy to get out of order positionally, and a reordering
mistake does not raise an error -- it just silently stores the wrong field
in the wrong column.

## Add a TUI field

Add one `DashboardColumn` to `ui/dashboard.py`:

```python
DashboardColumn(
    "Memory",
    "memory",
    "TotalMemory",
    " GiB",
    0,
)
```

No database migration is required.

## Tests

Run:

```bash
pytest
```

Component tests use synthetic Redfish data and do not require a physical BMC.

A new collector's test must assert `value`, `unit`, `health`, and `state` --
not only `value`. A sensor can have the right number and still have the
wrong unit or health information attached to it.

## Design rule

Keep this boundary:

```text
Redfish JSON
     ↓
component collector
     ↓
Metric
     ↓
DuckDB
     ↓
Textual
```

The UI should not know Redfish URLs or JSON structure.

## Security

Never commit BMC passwords. Use environment variables.


## Adding graph data

Graphs use the same `Metric` history already stored in DuckDB. For a new
telemetry graph:

1. Add a component collector in `redfish/components.py`.
2. Return timestamped `Metric` objects.
3. Store them through the existing collector/database path.
4. Add the metric to `ui/dashboard.py`'s graph queries and rendering only if
   it belongs in the default dashboard.

Do not introduce a web server or browser dependency for terminal graphs.


## Database values

Numeric metrics must use `Metric.value` and text states must use `Metric.text_value`. Do not stringify numeric telemetry before inserting it into DuckDB. This keeps graph/history queries numeric and prevents non-numeric values from silently disappearing from graphs.

## Redfish clients

The application creates one `RedfishClient` per configured node and reuses it across polling cycles. Collectors should use the provided client rather than creating their own HTTP client.

## BMC discovery

Prefer `--network` when possible. If no network is specified, discovery shows the detected local networks and asks for confirmation before scanning them. Use `--yes` only for trusted, unattended test-machine workflows.
