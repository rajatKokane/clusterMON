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
            512,
            "GiB",
            "OK",
            "Enabled",
        )
    ]
```

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
