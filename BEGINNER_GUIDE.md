# ClusterMON Beginner Guide

Welcome to ClusterMON.

This guide is for someone who has just received ClusterMON and is thinking:

> "I have the files. What the hell do I do with them?"

That's exactly what this document is for.

You do **not** need to understand the ClusterMON source code to use it.

---

# 1. What is ClusterMON?

ClusterMON is a terminal-based monitoring tool for servers and their BMCs.

It connects to the BMC of each server using **Redfish**, collects a few useful pieces of information, stores the readings locally, and displays them in a terminal dashboard.

At a high level:

```text
             Server 1 BMC
                  │
             Server 2 BMC
                  │
             Server 3 BMC
                  │
                  ▼
             Redfish
                  │
                  ▼
             ClusterMON
              /       \
             /         \
       DuckDB          TUI
      (history)     (terminal)
```

The important part is this:

**ClusterMON is a terminal application.**

You do not need:

- A web browser
- Grafana
- Prometheus
- A web server
- Kubernetes
- A separate database server

You run ClusterMON in a terminal and see the cluster there.

---

# 2. What does ClusterMON monitor?

The current version focuses on a small number of useful metrics:

- Server power state
- CPU die temperature
- Average fan speed
- Node collection status
- Historical graphs

ClusterMON deliberately does **not** try to monitor everything a server can possibly expose.

You don't need 500 numbers on the screen just because the BMC provides 500 numbers.

---

# 3. Before you start

You need:

1. A Linux machine where ClusterMON will run.
2. Network access from that machine to the BMCs.
3. Python 3.9 or newer.
4. The username and password used to log into the BMC.
5. The BMCs must provide a Redfish interface.

In a factory or validation environment, it is perfectly reasonable to run ClusterMON from your test machine.

---

# 4. Install ClusterMON

First, enter the ClusterMON directory:

```bash
cd cluster-mon
```

Create a Python virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

---

# 5. Find your BMCs

If you already know the BMC IP addresses, you can enter them manually.

If you have several BMCs on a test network, ClusterMON can discover Redfish BMCs for you.

For example, suppose your BMC network is:

```text
172.16.1.0/24
```

Run:

```bash
python tools/discover_bmcs.py --network 172.16.1.0/24
```

ClusterMON checks the specified network for Redfish endpoints.

It is looking for something that responds to:

```text
https://<BMC-IP>/redfish/v1/
```

Specify the network you actually want to scan. Do not blindly scan every network connected to a laptop that also happens to be connected to a corporate LAN or VPN.

---

# 6. What does discovery create?

The discovery tool creates or updates:

```text
config.json
```

This file tells ClusterMON which BMCs it should monitor.

It will look roughly like this:

```json
{
    "nodes": [
        {
            "node_id": "node-172-16-1-16",
            "bmc_url": "https://172.16.1.16",
            "username": "root",
            "password_env": "CLUSTERMON_BMC_PASSWORD",
            "verify_ssl": false
        }
    ]
}
```

You do **not** put the BMC password into this file.

---

# 7. Give ClusterMON the BMC password

ClusterMON reads the BMC password from an environment variable.

For example:

```bash
export CLUSTERMON_BMC_PASSWORD='your-bmc-password'
```

The configuration contains the **name** of the environment variable. The shell contains the actual password.

Do not put the password into `config.json` or commit it to Git.

---

# 8. Start ClusterMON

Once `config.json` exists and the password variable has been exported:

```bash
python app.py
```

ClusterMON periodically contacts the BMCs and updates the terminal dashboard.

The normal polling interval is currently 5 seconds.

---

# 9. Understanding the dashboard

The dashboard contains information about each configured node.

You will see information such as:

- Power
- CPU Die 1
- CPU Die 2
- Average Fan RPM
- Health
- Status
- Last Update

### Power

The server's reported chassis power state, such as `ON` or `OFF`.

### CPU Die 1 / CPU Die 2

The CPU die temperatures reported by the BMC. ClusterMON intentionally does not display every individual CPU-core temperature.

### Average Fan RPM

An average of the available RPM-based fan readings.

### Health

Health information reported by the monitored system/BMC. Treat it as a useful status indicator, not an absolute statement that every component is healthy.

### Status

This describes ClusterMON's ability to communicate with the node.

- `ONLINE`: collection succeeded.
- `TIMEOUT`: the BMC did not respond within the expected time.
- `ERROR`: collection failed for another reason.

A `TIMEOUT` does not necessarily mean the server itself is broken. The BMC or network connection may be the problem.

---

# 10. Looking at graphs

ClusterMON keeps historical metric data locally so the TUI can display graphs.

A graph lets you see a trend rather than only the latest value.

For example:

```text
Temperature

80 C ┤                         ╭──╮
70 C ┤                   ╭─────╯  ╰──
60 C ┤          ╭────────╯
50 C ┤──────────╯
    └───────────────────────────────
       15 minutes              Now
```

This is useful when a problem develops gradually.

---

# 11. Scenario: monitoring a factory test network

Suppose you are testing three servers.

Your test machine is connected to:

```text
172.16.1.0/24
```

You do not remember the BMC addresses and want ClusterMON to find them.

### Step 1: Enter the project

```bash
cd cluster-mon
```

### Step 2: Activate the Python environment

```bash
source .venv/bin/activate
```

### Step 3: Discover the BMCs

```bash
python tools/discover_bmcs.py --network 172.16.1.0/24
```

The tool finds the Redfish BMCs and writes them to `config.json`.

### Step 4: Set the password

```bash
export CLUSTERMON_BMC_PASSWORD='your-bmc-password'
```

### Step 5: Start monitoring

```bash
python app.py
```

You now have a terminal dashboard showing your servers.

---

# 12. Adding another BMC

If you add another server, run discovery again:

```bash
python tools/discover_bmcs.py --network 172.16.1.0/24
```

The configuration is updated with newly discovered BMCs.

You do not need to modify the Python source code just to add another server.

---

# 13. What if I already know the BMC IP?

You can edit `config.json` directly.

For example:

```json
{
    "nodes": [
        {
            "node_id": "test-server-01",
            "bmc_url": "https://172.16.1.16",
            "username": "root",
            "password_env": "CLUSTERMON_BMC_PASSWORD",
            "verify_ssl": false
        }
    ]
}
```

Then:

```bash
export CLUSTERMON_BMC_PASSWORD='your-bmc-password'
python app.py
```

---

# 14. Why is `verify_ssl` set to false?

Many BMCs use self-signed HTTPS certificates.

For a controlled local management network, ClusterMON can therefore be configured with:

```json
"verify_ssl": false
```

This is convenient for lab and factory environments. For a production environment with properly managed certificates, certificate verification should be enabled.

---

# 15. Where is the historical data stored?

ClusterMON uses DuckDB for local metric history.

You do not need to install or configure a database server.

The database is a local file, normally:

```text
cluster_mon.duckdb
```

The TUI reads historical data from it when displaying graphs.

---

# 16. What files should I care about?

The most important files are:

```text
cluster-mon/
│
├── app.py
│       Main application.
│
├── config.json
│       Your BMC configuration.
│
├── config.example.json
│       Example configuration.
│
├── requirements.txt
│       Python dependencies.
│
├── tools/
│   └── discover_bmcs.py
│       BMC discovery tool.
│
├── redfish/
│       Redfish communication and data collection.
│
├── database/
│       DuckDB storage.
│
├── ui/
│       Terminal user interface.
│
└── cluster_mon.duckdb
        Local metric history.
```

As a normal user, you generally only need to care about `config.json`, `tools/discover_bmcs.py`, `cluster_mon.duckdb`, and `app.py`.

---

# 17. I want to monitor a new sensor

This is one of the main reasons ClusterMON is structured the way it is.

Suppose your BMC exposes something that ClusterMON does not currently show:

```text
CPU temperature       ← already supported
Fan RPM               ← already supported
Power state           ← already supported

Memory temperature    ← not currently supported
GPU temperature       ← not currently supported
Board temperature     ← not currently supported
```

You should not need to rewrite the application to add one sensor.

The basic process is:

```text
1. Find the sensor in Redfish
        ↓
2. Write a small collector
        ↓
3. Register the collector
        ↓
4. Add it to the TUI
        ↓
5. Test it
```

## 17.1 Find the sensor in Redfish

Before changing Python code, find out how the BMC exposes the sensor.

A useful starting point is:

```bash
curl -k -u root https://<BMC-IP>/redfish/v1/
```

The exact Redfish path depends on the BMC implementation. Thermal information is commonly available under a path similar to:

```text
/redfish/v1/Chassis/<chassis>/Thermal
```

Look at the actual JSON returned by your BMC. Do not assume every BMC uses identical field names.

For example, you might find:

```json
{
    "Temperatures": [
        {
            "MemberId": "Memory_1",
            "Name": "Memory Temperature",
            "ReadingCelsius": 42.5,
            "Status": {
                "Health": "OK",
                "State": "Enabled"
            }
        }
    ]
}
```

Now we know:

```text
MemberId       → Memory_1
Name           → Memory Temperature
ReadingCelsius → 42.5
Health         → OK
State          → Enabled
```

That is the information the collector needs.

## 17.2 Add the collector

ClusterMON keeps Redfish parsing in:

```text
redfish/components.py
```

Add a small function for the new sensor. For example:

```python
def collect_memory_temperatures(node_id, thermal, timestamp):
    metrics = []

    for sensor in thermal.get("Temperatures", []):
        member_id = sensor.get("MemberId", "")

        if not member_id.startswith("Memory_"):
            continue

        status = sensor.get("Status", {})

        metrics.append(
            Metric(
                node_id,
                timestamp,
                "temperature",
                member_id,
                sensor.get("Name", member_id),
                value=sensor.get("ReadingCelsius"),
                unit="C",
                health=status.get("Health"),
                state=status.get("State"),
            )
        )

    return metrics
```

Use keyword arguments for the optional metric fields. This makes the code much harder to break if the `Metric` model changes later.

## 17.3 Register the collector

Writing the function is not enough. ClusterMON needs to call it.

Open:

```text
redfish/collector.py
```

Find where the existing component collectors are called and add your new collector there.

The flow should be:

```text
BMC Redfish JSON
       ↓
RedfishCollector
       ↓
collect_memory_temperatures()
       ↓
Metric
       ↓
DuckDB
```

## 17.4 Do I need to change the database?

Normally, **no**.

ClusterMON stores generic metrics rather than having a separate database table for every sensor.

For example:

```text
CPU temperature
    category = temperature
    member_id = Die_CPU1

Memory temperature
    category = temperature
    member_id = Memory_1

Fan speed
    category = fan
    member_id = AverageRPM
```

The database does not need a new table for every new sensor.

## 17.5 Add the sensor to the TUI

If you want the new sensor to appear in the main dashboard, open:

```text
ui/dashboard.py
```

The dashboard uses `DashboardColumn` definitions.

For example:

```python
DashboardColumn(
    "Memory Temp",
    "temperature",
    "Memory_1",
    " C",
    1,
)
```

The important fields are:

```text
"Memory Temp"   → what the user sees
"temperature"   → metric category
"Memory_1"      → metric member_id
" C"            → displayed suffix
1                → decimal places
```

The `member_id` must match what your collector puts into the `Metric`.

## 17.6 What if there are many sensors?

Suppose the BMC reports 64 memory temperature sensors.

You probably do not want 64 columns in the terminal.

You can instead create an aggregate such as:

```text
Average Memory Temperature
Maximum Memory Temperature
```

The point is to expose useful information, not reproduce the entire BMC JSON document in the terminal.

## 17.7 Add a test

A new collector should have a test under:

```text
tests/
```

At minimum, test:

```text
value
unit
health
state
member_id
```

For example:

```python
metrics = collect_memory_temperatures(
    "test-server-01",
    THERMAL_DATA,
    timestamp,
)

assert len(metrics) == 1
assert metrics[0].member_id == "Memory_1"
assert metrics[0].value == 42.5
assert metrics[0].unit == "C"
assert metrics[0].health == "OK"
assert metrics[0].state == "Enabled"
```

Checking only `value` is not enough. A sensor can have the right number and still have the wrong unit or health information.

## 17.8 Run the tests

From the ClusterMON directory:

```bash
pytest
```

Then test against a real BMC.

## 17.9 Test the actual Redfish data

Before assuming the collector works, inspect what the BMC actually sends:

```bash
curl -k -u root https://<BMC-IP>/redfish/v1/Chassis/<chassis>/Thermal
```

BMC implementations can use different `MemberId` and naming conventions for similar sensors. Use the actual response from your hardware as the source of truth.

## 17.10 Complete example

Suppose you want to add **board temperature** and discover this Redfish object:

```json
{
    "MemberId": "BoardTemp",
    "Name": "Main Board Temperature",
    "ReadingCelsius": 36.4,
    "Status": {
        "Health": "OK",
        "State": "Enabled"
    }
}
```

### Step 1

Add a collector in `redfish/components.py`.

```python
def collect_board_temperature(node_id, thermal, timestamp):
    for sensor in thermal.get("Temperatures", []):
        if sensor.get("MemberId") != "BoardTemp":
            continue

        status = sensor.get("Status", {})

        return [
            Metric(
                node_id,
                timestamp,
                "temperature",
                "BoardTemp",
                sensor.get("Name", "Board Temperature"),
                value=sensor.get("ReadingCelsius"),
                unit="C",
                health=status.get("Health"),
                state=status.get("State"),
            )
        ]

    return []
```

### Step 2

Call it from `redfish/collector.py`.

### Step 3

Add this to `ui/dashboard.py`:

```python
DashboardColumn(
    "Board Temp",
    "temperature",
    "BoardTemp",
    " C",
    1,
)
```

### Step 4

Add a test.

### Step 5

Run:

```bash
pytest
```

### Step 6

Run ClusterMON:

```bash
python app.py
```

You should now see the new sensor in the dashboard.

## 17.11 The rule to remember

When adding a sensor, follow this path:

```text
       REDFISH
          │
          ▼
┌─────────────────────┐
│ components.py       │
│ Parse the JSON      │
│ into Metric objects │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ collector.py        │
│ Collect the metric  │
└──────────┬──────────┘
           │
           ▼
       DATABASE
           │
           ▼
┌─────────────────────┐
│ dashboard.py        │
│ Display the metric  │
└─────────────────────┘
```

Remember:

> **Redfish parsing belongs in `components.py`. Collection orchestration belongs in `collector.py`. Display configuration belongs in `dashboard.py`.**

Do not put Redfish JSON parsing into the TUI.

Do not make the database know what a DIMM or CPU is.

Do not make the dashboard call Redfish directly.

Keep each piece doing one job.

---

# 18. Common problems

## The BMC isn't detected

Check network connectivity:

```bash
ping <BMC-IP>
```

Then check the Redfish endpoint:

```bash
curl -k https://<BMC-IP>/redfish/v1/
```

You should receive a Redfish response.

## The node says TIMEOUT

Check:

1. Is the BMC powered on?
2. Can the test machine reach the BMC?
3. Is the BMC network accessible?
4. Is the BMC responding to HTTPS?

## The node says ERROR

Run with debug logging:

```bash
python app.py --debug
```

This provides additional information about authentication, network communication, Redfish data, configuration, or other application errors.

## The password environment variable is missing

Check:

```bash
echo "$CLUSTERMON_BMC_PASSWORD"
```

If nothing is printed:

```bash
export CLUSTERMON_BMC_PASSWORD='your-bmc-password'
```

Then start ClusterMON again.

---

# 19. Stopping ClusterMON

ClusterMON runs in the terminal.

To stop it:

```text
Ctrl+C
```

There is no service to stop and no web server to shut down.

---

# 20. The five commands you actually need

For a typical test-machine setup:

```bash
cd cluster-mon
source .venv/bin/activate
python tools/discover_bmcs.py --network 172.16.1.0/24
export CLUSTERMON_BMC_PASSWORD='your-bmc-password'
python app.py
```

Once ClusterMON is running, you are looking at the cluster from your terminal.

---

# 21. Quick mental model

If you forget everything else, remember this:

```text
                 YOUR TEST MACHINE
                       │
                 ┌─────▼─────┐
                 │ ClusterMON│
                 └─────┬─────┘
                       │
                  Redfish/HTTPS
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       BMC #1       BMC #2       BMC #3
          │            │            │
       Server        Server       Server
```

ClusterMON does four basic things:

```text
1. Find the BMCs
        ↓
2. Connect to them
        ↓
3. Collect useful information
        ↓
4. Show it in your terminal
```

That's the whole idea.

---

# 22. One-page cheat sheet

### First-time setup

```bash
cd cluster-mon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Discover BMCs

```bash
python tools/discover_bmcs.py --network 172.16.1.0/24
```

### Set password

```bash
export CLUSTERMON_BMC_PASSWORD='your-bmc-password'
```

### Start

```bash
python app.py
```

### Debug

```bash
python app.py --debug
```

### Stop

```text
Ctrl+C
```

### Files to remember

```text
config.json             → Which BMCs to monitor
CLUSTERMON_BMC_PASSWORD → BMC password
cluster_mon.duckdb      → Historical data
app.py                  → Start ClusterMON
```

### The important rule

**Never put the BMC password directly into `config.json`.**

---

# 23. That's it

If you can get from:

```text
"I have a test machine and some BMCs"
```

to:

```bash
python app.py
```

then you are using ClusterMON correctly.

Everything else is implementation detail.
