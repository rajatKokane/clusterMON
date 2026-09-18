import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NodeConfig:
    node_id: str
    bmc_url: str
    username: str
    password: str
    verify_ssl: bool = False


def load_nodes(path="config.json"):
    config_path = Path(path)

    if not config_path.exists():
        raise RuntimeError(
            "Configuration file {!r} does not exist. "
            "Copy config.example.json to config.json first.".format(str(config_path))
        )

    try:
        with config_path.open("r", encoding="utf-8") as file:
            raw_config = json.load(file)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid JSON in {!r}: {}".format(str(config_path), exc)
        )

    configured_nodes = raw_config.get("nodes")
    if not isinstance(configured_nodes, list):
        raise RuntimeError("config.json must contain a 'nodes' list")

    nodes = []

    for entry in configured_nodes:
        if not isinstance(entry, dict):
            raise RuntimeError("Each node entry in config.json must be an object")

        required = ("node_id", "bmc_url", "password_env")
        missing = [key for key in required if not entry.get(key)]

        if missing:
            raise RuntimeError(
                "Node configuration is missing required field(s): {}".format(
                    ", ".join(missing)
                )
            )

        password_env = entry["password_env"]
        password = os.environ.get(password_env)

        if not password:
            raise RuntimeError(
                "Missing BMC password environment variable {!r} for node {!r}".format(
                    password_env, entry["node_id"]
                )
            )

        nodes.append(
            NodeConfig(
                node_id=entry["node_id"],
                bmc_url=entry["bmc_url"].rstrip("/"),
                username=entry.get("username", "root"),
                password=password,
                verify_ssl=entry.get("verify_ssl", False),
            )
        )

    if not nodes:
        raise RuntimeError("No nodes configured in config.json")

    node_ids = [node.node_id for node in nodes]
    duplicates = {node_id for node_id in node_ids if node_ids.count(node_id) > 1}

    if duplicates:
        raise RuntimeError(
            "Duplicate node_id values found: " + ", ".join(sorted(duplicates))
        )

    return nodes
