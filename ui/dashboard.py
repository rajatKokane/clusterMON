from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static

from database.db import Database


@dataclass(frozen=True)
class DashboardColumn:
    title: str
    category: str
    member_id: str
    suffix: str = ""
    decimals: Optional[int] = None


# ADD A TUI FIELD HERE after adding its Metric collector.
# Example:
#
# DashboardColumn(
#     "Memory", "memory", "TotalMemory", " GiB", 0
# )
COLUMNS = [
    DashboardColumn("Power", "power", "PowerState"),
    DashboardColumn("CPU Die 1", "temperature", "Die_CPU1", " C", 1),
    DashboardColumn("CPU Die 2", "temperature", "Die_CPU2", " C", 1),
    DashboardColumn("Avg Fan RPM", "fan", "AverageRPM", " RPM", 0),
    DashboardColumn("Health", "power", "PowerState"),
]


class ClusterDashboard(Container):
    def __init__(self, database: Database, node_status: dict):
        super().__init__()
        self.database = database
        self.node_status = node_status

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("ClusterMON | Redfish Node Monitor", id="title")
        yield DataTable(id="nodes")
        yield Footer()

    def on_mount(self):
        table = self.query_one("#nodes", DataTable)
        table.add_columns(
            "Node",
            *[column.title for column in COLUMNS],
            "Status",
            "Last Update",
        )
        self.refresh_data()

    def refresh_data(self):
        table = self.query_one("#nodes", DataTable)
        table.clear()

        rows = defaultdict(dict)

        for row in self.database.fetch_latest_snapshot():
            (
                node_id,
                timestamp,
                category,
                member_id,
                name,
                value,
                unit,
                health,
                state,
            ) = row

            rows[node_id][(category, member_id)] = {
                "value": value,
                "health": health,
                "state": state,
            }
            rows[node_id]["timestamp"] = timestamp

        for node_id in self.node_status:
            rows.setdefault(node_id, {})

        for node_id, data in rows.items():
            values = [node_id]

            for column in COLUMNS:
                metric = data.get((column.category, column.member_id), {})

                if column.title == "Health":
                    values.append(str(metric.get("health") or "N/A"))
                else:
                    values.append(
                        self._format_value(
                            metric.get("value"),
                            column.suffix,
                            column.decimals,
                        )
                    )

            values.extend([
                self.node_status.get(node_id, "UNKNOWN"),
                str(data.get("timestamp", "N/A")),
            ])

            table.add_row(*values)

    @staticmethod
    def _format_value(value, suffix, decimals):
        if value is None:
            return "N/A"

        if decimals is not None:
            try:
                return "{:.{}f}{}".format(float(value), decimals, suffix)
            except (TypeError, ValueError):
                pass

        return "{}{}".format(value, suffix)
