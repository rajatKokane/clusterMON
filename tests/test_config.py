import json

import pytest

from config import load_nodes


def test_load_nodes_reads_password_from_environment(tmp_path, monkeypatch):
    path = tmp_path / "config.json"

    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "node_id": "node01",
                        "bmc_url": "https://172.16.1.16",
                        "password_env": "NODE01_PASSWORD",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("NODE01_PASSWORD", "secret")

    nodes = load_nodes(str(path))

    assert len(nodes) == 1
    assert nodes[0].node_id == "node01"
    assert nodes[0].password == "secret"


def test_load_nodes_rejects_missing_password(tmp_path, monkeypatch):
    path = tmp_path / "config.json"

    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "node_id": "node01",
                        "bmc_url": "https://172.16.1.16",
                        "password_env": "MISSING_PASSWORD",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("MISSING_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Missing BMC password"):
        load_nodes(str(path))


def test_load_nodes_rejects_duplicate_node_ids(tmp_path, monkeypatch):
    path = tmp_path / "config.json"

    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "node_id": "node01",
                        "bmc_url": "https://172.16.1.16",
                        "password_env": "P1",
                    },
                    {
                        "node_id": "node01",
                        "bmc_url": "https://172.16.1.17",
                        "password_env": "P2",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("P1", "secret")
    monkeypatch.setenv("P2", "secret")

    with pytest.raises(RuntimeError, match="Duplicate node_id"):
        load_nodes(str(path))
