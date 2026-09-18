from datetime import datetime, timezone

from redfish.client import RedfishClient
from redfish.components import (
    collect_average_fan_speed,
    collect_cpu_die_temperatures,
    collect_power,
)


class RedfishCollector:
    """Collect the Redfish resources required by v0.1."""

    def __init__(self, client: RedfishClient, node_id: str):
        self.client = client
        self.node_id = node_id

    async def collect(self):
        timestamp = datetime.now(timezone.utc)

        root = await self.client.get("/redfish/v1/")

        chassis_collection = await self.client.get(root["Chassis"]["@odata.id"])
        members = chassis_collection.get("Members", [])

        if not members:
            raise RuntimeError("Redfish Chassis collection contains no members")

        chassis = await self.client.get(members[0]["@odata.id"])

        metrics = collect_power(self.node_id, chassis, timestamp)

        thermal_uri = chassis.get("Thermal", {}).get("@odata.id")
        if not thermal_uri:
            return metrics

        thermal = await self.client.get(thermal_uri)

        metrics.extend(
            collect_cpu_die_temperatures(
                self.node_id, thermal, timestamp
            )
        )
        metrics.extend(
            collect_average_fan_speed(
                self.node_id, thermal, timestamp
            )
        )

        return metrics
