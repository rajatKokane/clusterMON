import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from textual.app import App

from config import load_nodes
from database.db import Database
from models import CollectionResult
from redfish.client import RedfishClient
from redfish.collector import RedfishCollector
from ui.dashboard import ClusterDashboard


LOGGER = logging.getLogger("clustermon")


def configure_logging(debug):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def collect_node(node):
    timestamp = datetime.now(timezone.utc)

    try:
        async with RedfishClient(
            node.bmc_url,
            node.username,
            node.password,
            verify_ssl=node.verify_ssl,
        ) as client:
            metrics = await RedfishCollector(
                client,
                node.node_id,
            ).collect()

            LOGGER.debug(
                "Collected %d metrics from %s",
                len(metrics),
                node.node_id,
            )

            return CollectionResult(
                node.node_id,
                timestamp,
                metrics,
                "ONLINE",
            )

    except asyncio.TimeoutError:
        LOGGER.error("Timeout collecting %s", node.node_id)
        return CollectionResult(
            node.node_id,
            timestamp,
            [],
            "TIMEOUT",
            "Request timed out",
        )

    except Exception as exc:
        LOGGER.error("Collection failed for %s: %s", node.node_id, exc)
        return CollectionResult(
            node.node_id,
            timestamp,
            [],
            "ERROR",
            str(exc),
        )


async def collect_all(nodes):
    return await asyncio.gather(*(collect_node(node) for node in nodes))


class ClusterMON(App):
    TITLE = "ClusterMON"

    CSS = '''
    Screen {
        layout: vertical;
    }

    #title {
        height: 1;
        content-align: center middle;
    }

    #nodes {
        height: 1fr;
        margin: 1 2;
    }
    '''

    def __init__(self, nodes, database_path):
        super().__init__()
        self.nodes = nodes
        self.database = Database(database_path)
        self.node_status = {
            node.node_id: "STARTING"
            for node in nodes
        }

    def compose(self):
        yield ClusterDashboard(self.database, self.node_status)

    async def on_mount(self):
        await self.collect_and_refresh()
        self.set_interval(5, self.collect_and_refresh)

    async def collect_and_refresh(self):
        results = await collect_all(self.nodes)

        for result in results:
            self.node_status[result.node_id] = result.status

            if result.metrics:
                self.database.insert_metrics(result.metrics)

        self.query_one(ClusterDashboard).refresh_data()

    def on_unmount(self):
        self.database.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="ClusterMON Redfish cluster monitoring TUI"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to node configuration JSON",
    )
    parser.add_argument(
        "--database",
        default="cluster_mon.duckdb",
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    configure_logging(args.debug)

    try:
        nodes = load_nodes(args.config)
        ClusterMON(nodes, args.database).run()
    except Exception as exc:
        LOGGER.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
