#!/usr/bin/env python3
"""Run fake Redfish BMCs on localhost so ClusterMON can be exercised without
real hardware.

Starts a small mock BMC fleet and writes a node config pointing at them.
Run this in one terminal, then point the real app at the generated config
in another terminal:

Examples:
    python tools/simulate.py
    python tools/simulate.py --nodes 10
    python tools/simulate.py --config sim_config.json --base-port 9200

    # in a second terminal:
    python app.py --config sim_config.json --database sim.duckdb

The default fleet is three nodes chosen to show the three states the
dashboard can be in at once: a healthy node, a node with a Critical
temperature sensor, and a node that never responds (Status: ERROR).
--nodes adds more healthy nodes on top of those three, for basic
concurrency/load exercising.

Nothing here talks to the network beyond 127.0.0.1 -- no real BMC, no
credentials, no risk of scanning or touching anything that isn't this
process.
"""

import argparse
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_CONFIG = "sim_config.json"
DEFAULT_BASE_PORT = 9101


def thermal_payload(base_temp, health="OK", jitter=1.5):
    t1 = round(base_temp + random.uniform(-jitter, jitter), 1)
    t2 = round(base_temp + random.uniform(-jitter, jitter) + 1.0, 1)
    return {
        "Temperatures": [
            {"MemberId": "Die_CPU1", "Name": "Die CPU1", "ReadingCelsius": t1,
             "Status": {"Health": health, "State": "Enabled"}},
            {"MemberId": "Die_CPU2", "Name": "Die CPU2", "ReadingCelsius": t2,
             "Status": {"Health": "OK", "State": "Enabled"}},
            {"MemberId": "Core_0_CPU1", "Name": "Core 0 CPU1",
             "ReadingCelsius": round(t1 + 4, 1), "Status": {"Health": "OK", "State": "Enabled"}},
        ],
        "Fans": [
            {"Reading": random.randint(3200, 3400), "ReadingUnits": "RPM"},
            {"Reading": random.randint(3150, 3350), "ReadingUnits": "RPM"},
        ],
    }


def make_routes(power_state="On", chassis_health="OK", temp_health="OK", down=False):
    def routes(path):
        if down:
            return None  # drop the connection -- simulates an unreachable BMC
        if path == "/redfish/v1/":
            return 200, {"Chassis": {"@odata.id": "/redfish/v1/Chassis"}}
        if path == "/redfish/v1/Chassis":
            return 200, {"Members": [{"@odata.id": "/redfish/v1/Chassis/1"}]}
        if path == "/redfish/v1/Chassis/1":
            return 200, {
                "PowerState": power_state,
                "Status": {"Health": chassis_health, "State": "Enabled"},
                "Thermal": {"@odata.id": "/redfish/v1/Chassis/1/Thermal"},
            }
        if path == "/redfish/v1/Chassis/1/Thermal":
            base = 42.0 if temp_health == "OK" else 88.0
            return 200, thermal_payload(base, health=temp_health)
        return 404, {"error": "not found"}
    return routes


class MockRedfishHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        result = self.server.routes(self.path)
        if result is None:
            return  # connection dropped, no response -- simulates a dead BMC
        status, body = result
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_mock(port, **profile):
    server = ThreadingHTTPServer(("127.0.0.1", port), MockRedfishHandler)
    server.routes = make_routes(**profile)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def build_fleet(total_nodes, base_port):
    fleet = [
        ("node-sim-healthy", base_port, dict(power_state="On", chassis_health="OK", temp_health="OK")),
        ("node-sim-critical-sensor", base_port + 1,
         dict(power_state="On", chassis_health="Warning", temp_health="Critical")),
        ("node-sim-unreachable", base_port + 2, dict(down=True)),
    ]
    for index in range(3, total_nodes):
        fleet.append((
            "node-sim-extra-{:02d}".format(index - 2),
            base_port + index,
            dict(power_state="On", chassis_health="OK", temp_health="OK"),
        ))
    return fleet


def write_config(fleet, config_path):
    nodes = [
        {
            "node_id": node_id,
            "bmc_url": "http://127.0.0.1:{}".format(port),
            "username": "root",
            "password_env": "CLUSTERMON_SIM_PASSWORD",
            "verify_ssl": False,
        }
        for node_id, port, _profile in fleet
    ]
    Path(config_path).write_text(json.dumps({"nodes": nodes}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run fake Redfish BMCs for exercising ClusterMON.")
    parser.add_argument("--nodes", type=int, default=3, help="Total simulated nodes (minimum 3, default 3)")
    parser.add_argument("--base-port", type=int, default=DEFAULT_BASE_PORT, help="First mock BMC port")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Where to write the generated node config")
    args = parser.parse_args()

    total_nodes = max(3, args.nodes)
    fleet = build_fleet(total_nodes, args.base_port)

    for node_id, port, profile in fleet:
        start_mock(port, **profile)

    write_config(fleet, args.config)

    print("Mock BMCs running:")
    for node_id, port, _profile in fleet:
        print("  {:<28} http://127.0.0.1:{}".format(node_id, port))
    print("\nConfig written to {}".format(args.config))
    print("\nIn another terminal:")
    print("  export CLUSTERMON_SIM_PASSWORD=unused")
    print("  python app.py --config {} --database sim.duckdb".format(args.config))
    print("\nCtrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
