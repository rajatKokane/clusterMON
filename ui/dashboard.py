from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical
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

GRAPH_WINDOW_MINUTES = 15
GRAPH_WIDTH = 72
GRAPH_HEIGHT = 8


class ClusterDashboard(Container):
    def __init__(self, database: Database, node_status: dict):
        super().__init__()
        self.database = database
        self.node_status = node_status
        self.selected_node_id = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("ClusterMON | Redfish Node Monitor", id="title")
        yield DataTable(id="nodes")
        yield Vertical(
            Static("Select a node to view telemetry history", id="graph-title"),
            Static("", id="graphs"),
            id="graph-panel",
        )
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Change the graph target when the operator selects a node."""
        self.selected_node_id = str(event.row_key.value)
        self.refresh_graph()

    def refresh_data(self):
        table = self.query_one("#nodes", DataTable)
        current_row = table.cursor_row
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
                text_value,
                unit,
                health,
                state,
            ) = row

            rows[node_id][(category, member_id)] = {
                "value": value,
                "text_value": text_value,
                "health": health,
                "state": state,
            }
            rows[node_id]["timestamp"] = timestamp

        for node_id in self.node_status:
            rows.setdefault(node_id, {})

        node_ids = list(rows.keys())

        for node_id, data in rows.items():
            values = [node_id]

            for column in COLUMNS:
                metric = data.get((column.category, column.member_id), {})

                if column.title == "Health":
                    values.append(str(metric.get("health") or "N/A"))
                else:
                    display_value = (
                        metric.get("text_value")
                        if column.category == "power"
                        else metric.get("value")
                    )
                    values.append(
                        self._format_value(
                            display_value,
                            column.suffix,
                            column.decimals,
                        )
                    )

            values.extend([
                self.node_status.get(node_id, "UNKNOWN"),
                str(data.get("timestamp", "N/A")),
            ])

            table.add_row(*values, key=node_id)

        if self.selected_node_id not in node_ids:
            self.selected_node_id = node_ids[0] if node_ids else None

        if node_ids and current_row >= 0:
            table.move_cursor(row=min(current_row, len(node_ids) - 1))

        self.refresh_graph()

    def refresh_graph(self):
        graph_title = self.query_one("#graph-title", Static)
        graph = self.query_one("#graphs", Static)

        if not self.selected_node_id:
            graph_title.update("Select a node to view telemetry history")
            graph.update("No node data available.")
            return

        graph_title.update(
            "Telemetry history | {} | last {} minutes".format(
                self.selected_node_id,
                GRAPH_WINDOW_MINUTES,
            )
        )

        cpu1 = self.database.fetch_history(
            self.selected_node_id,
            "temperature",
            "Die_CPU1",
            GRAPH_WINDOW_MINUTES,
        )
        cpu2 = self.database.fetch_history(
            self.selected_node_id,
            "temperature",
            "Die_CPU2",
            GRAPH_WINDOW_MINUTES,
        )
        fans = self.database.fetch_history(
            self.selected_node_id,
            "fan",
            "AverageRPM",
            GRAPH_WINDOW_MINUTES,
        )

        graph.update(
            "\n\n".join([
                self._render_graph(
                    "CPU temperature",
                    [
                        ("CPU1", cpu1),
                        ("CPU2", cpu2),
                    ],
                    " C",
                ),
                self._render_graph(
                    "Average fan speed",
                    [("Fan", fans)],
                    " RPM",
                ),
            ])
        )

    @staticmethod
    def _render_graph(title, series, unit):
        parsed = []
        for label, points in series:
            values = []
            for timestamp, value in points:
                try:
                    values.append((timestamp, float(value)))
                except (TypeError, ValueError):
                    continue
            if values:
                parsed.append((label, values))

        if not parsed:
            return "{}\n  No history collected yet.".format(title)

        all_values = [value for _, points in parsed for _, value in points]
        minimum = min(all_values)
        maximum = max(all_values)

        if minimum == maximum:
            padding = max(abs(minimum) * 0.05, 1.0)
            minimum -= padding
            maximum += padding

        # Keep a fixed number of columns so the graph does not jump around as
        # the terminal changes size. Each series is rendered independently.
        rendered = [title]
        for label, points in parsed:
            buckets = ClusterDashboard._resample(points, GRAPH_WIDTH)
            rows = [list(" " * GRAPH_WIDTH) for _ in range(GRAPH_HEIGHT)]

            for index, value in enumerate(buckets):
                if value is None:
                    continue
                normalized = (value - minimum) / (maximum - minimum)
                row = GRAPH_HEIGHT - 1 - int(
                    normalized * (GRAPH_HEIGHT - 1)
                )
                row = max(0, min(GRAPH_HEIGHT - 1, row))
                rows[row][index] = "█"

                # Connect adjacent points vertically to make sparse samples
                # easier to read without requiring a plotting dependency.
                if index > 0 and buckets[index - 1] is not None:
                    previous = buckets[index - 1]
                    previous_norm = (previous - minimum) / (maximum - minimum)
                    previous_row = GRAPH_HEIGHT - 1 - int(
                        previous_norm * (GRAPH_HEIGHT - 1)
                    )
                    step = 1 if row > previous_row else -1
                    for fill_row in range(previous_row, row, step):
                        rows[fill_row][index] = "│"

            latest = points[-1][1]
            rendered.append(
                "{:<5} {:>7.1f}{}".format(label, latest, unit)
            )
            rendered.extend("      " + "".join(row) for row in rows)
            rendered.append(
                "      {:>7.1f}{}".format(minimum, unit)
                + " " * max(0, GRAPH_WIDTH - 20)
                + "now {:>7.1f}{}".format(maximum, unit)
            )

        return "\n".join(rendered)

    @staticmethod
    def _resample(points, width):
        if len(points) <= width:
            values = [None] * width
            start = width - len(points)
            for index, (_, value) in enumerate(points):
                values[start + index] = value
            return values

        values = []
        bucket_size = len(points) / float(width)
        for index in range(width):
            start = int(index * bucket_size)
            end = max(start + 1, int((index + 1) * bucket_size))
            bucket = points[start:end]
            values.append(sum(value for _, value in bucket) / len(bucket))
        return values

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
