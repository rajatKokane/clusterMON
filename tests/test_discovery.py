import json
from pathlib import Path

from tools.discover_bmcs import build_config, shell_quote


def test_build_config_uses_shared_password_env():
    config = build_config(
        [{"ip": "172.16.1.16", "redfish_version": "1.15.0", "service_root_id": "redfish"}],
        {"nodes": []},
        "CLUSTERMON_BMC_PASSWORD",
    )
    assert config["nodes"] == [{
        "node_id": "node-172-16-1-16",
        "bmc_url": "https://172.16.1.16",
        "username": "root",
        "password_env": "CLUSTERMON_BMC_PASSWORD",
        "verify_ssl": False,
    }]


def test_existing_node_id_is_preserved():
    config = build_config(
        [{"ip": "172.16.1.16", "redfish_version": "1.15.0", "service_root_id": "redfish"}],
        {"nodes": [{"node_id": "test-server-01", "bmc_url": "https://172.16.1.16", "username": "admin", "password_env": "OLD", "verify_ssl": True}]},
        "CLUSTERMON_BMC_PASSWORD",
    )
    assert config["nodes"][0]["node_id"] == "test-server-01"
    assert config["nodes"][0]["username"] == "admin"
    assert config["nodes"][0]["password_env"] == "OLD"


def test_shell_quote_handles_single_quote():
    assert shell_quote("abc'def") == "'abc'\\''def'"


def test_choose_node_id_is_ip_based():
    from tools.discover_bmcs import choose_node_id
    assert choose_node_id({"ip": "172.16.1.16"}) == "node-172-16-1-16"
