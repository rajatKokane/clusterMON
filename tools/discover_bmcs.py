#!/usr/bin/env python3
"""Discover Redfish BMCs and generate/update ClusterMON configuration.

Examples:
    python tools/discover_bmcs.py
    python tools/discover_bmcs.py --network 172.16.1.0/24
    eval "$(python tools/discover_bmcs.py --export-password)"

Passwords are never written to config.json.  --export-password prompts for a
password without echoing it and prints a shell export suitable for eval.
"""

import argparse
import asyncio
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

DEFAULT_TIMEOUT = 1.5
DEFAULT_PASSWORD_ENV = "CLUSTERMON_BMC_PASSWORD"
DEFAULT_CONFIG = "config.json"


def local_networks() -> List[ipaddress.IPv4Network]:
    """Return connected IPv4 networks from Linux routing information."""
    try:
        result = subprocess.run(
            ["ip", "-4", "route", "show", "scope", "link"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Unable to determine local networks; use --network.") from exc

    networks = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        try:
            network = ipaddress.ip_network(parts[0], strict=False)
        except ValueError:
            continue
        if isinstance(network, ipaddress.IPv4Network) and network.prefixlen >= 24:
            networks.append(network)
    return list(dict.fromkeys(networks))


def parse_networks(values: List[str]) -> List[ipaddress.IPv4Network]:
    networks = []
    for value in values:
        network = ipaddress.ip_network(value, strict=False)
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError("Only IPv4 networks are supported.")
        if network.num_addresses > 256:
            raise ValueError(
                "%s is larger than /24; use a smaller subnet to avoid an accidental large scan." % network
            )
        networks.append(network)
    return list(dict.fromkeys(networks))


async def probe(ip: str, timeout: float) -> Optional[Dict[str, str]]:
    """Return basic Redfish identity if HTTPS Redfish is available."""
    url = "https://%s/redfish/v1/" % ip
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
        if response.status_code != 200:
            return None
        data = response.json()
        if not isinstance(data, dict) or not data.get("RedfishVersion"):
            return None

        return {
            "ip": ip,
            "redfish_version": str(data.get("RedfishVersion", "unknown")),
            "service_root_id": str(data.get("Id", "redfish")),
        }
    except (httpx.HTTPError, ValueError, OSError):
        return None


async def discover(networks: List[ipaddress.IPv4Network], timeout: float, concurrency: int) -> List[Dict[str, str]]:
    semaphore = asyncio.Semaphore(concurrency)

    async def limited(ip: str):
        async with semaphore:
            return await probe(ip, timeout)

    tasks = [limited(str(ip)) for network in networks for ip in network.hosts()]
    results = await asyncio.gather(*tasks)
    return [result for result in results if result]


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    value = value.strip("-._")
    return value or "node"


def choose_node_id(result: Dict[str, str]) -> str:
    return "node-%s" % result["ip"].replace(".", "-")


def load_existing(path: Path) -> Dict:
    if not path.exists():
        return {"nodes": []}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise ValueError("Existing config must contain a 'nodes' list.")
    return data


def build_config(discovered: List[Dict[str, str]], existing: Dict, password_env: str) -> Dict:
    old_nodes = {str(node.get("bmc_url", "")).rstrip("/"): node for node in existing.get("nodes", [])}
    nodes = []
    for result in discovered:
        url = "https://%s" % result["ip"]
        old = old_nodes.get(url)
        node_id = old.get("node_id") if old else choose_node_id(result)
        nodes.append(
            {
                "node_id": node_id,
                "bmc_url": url,
                "username": old.get("username", "root") if old else "root",
                "password_env": old.get("password_env", password_env) if old else password_env,
                "verify_ssl": False,
            }
        )
    return {"nodes": nodes}


def write_config(path: Path, config: Dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4)
        handle.write("\n")
    os.replace(temp, path)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover Redfish BMCs for ClusterMON.")
    parser.add_argument("--network", action="append", default=[], help="IPv4 subnet to scan, e.g. 172.16.1.0/24")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="ClusterMON config path")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-host HTTPS timeout")
    parser.add_argument("--concurrency", type=int, default=64, help="Maximum concurrent probes")
    parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV, help="Environment variable used for BMC password")
    parser.add_argument("--export-password", action="store_true", help="Prompt securely and print an export command")
    parser.add_argument("--no-write", action="store_true", help="Discover and print BMCs without modifying config.json")
    parser.add_argument("--yes", action="store_true", help="Confirm scanning all detected local networks without prompting")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.export_password:
        password = getpass("ClusterMON BMC password: ")
        print("export %s=%s" % (args.password_env, shell_quote(password)))
        return 0

    try:
        networks = parse_networks(args.network) if args.network else local_networks()
    except (ValueError, RuntimeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    if not networks:
        print("ERROR: no /24-or-smaller connected IPv4 network found; use --network.", file=sys.stderr)
        return 2

    if not args.network and not args.yes:
        preview = ", ".join(str(network) for network in networks)
        try:
            answer = input(
                "No --network given. Scan all connected subnets (%s)? [y/N] " % preview
            ).strip().lower()
        except EOFError:
            answer = ""
        if answer != "y":
            print("Aborted. Use --network to target a specific subnet.", file=sys.stderr)
            return 2

    print("Scanning: %s" % ", ".join(str(network) for network in networks), file=sys.stderr)
    discovered = asyncio.run(discover(networks, args.timeout, args.concurrency))

    if not discovered:
        print("No Redfish BMCs discovered.", file=sys.stderr)
        return 1

    print("Discovered %d Redfish BMC(s):" % len(discovered), file=sys.stderr)
    for result in discovered:
        print("  %s  Redfish %s" % (result["ip"], result["redfish_version"]), file=sys.stderr)

    config_path = Path(args.config)
    existing = load_existing(config_path)
    config = build_config(discovered, existing, args.password_env)

    if not args.no_write:
        write_config(config_path, config)
        print("Updated %s" % config_path, file=sys.stderr)
        print("Password variable: %s" % args.password_env, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
