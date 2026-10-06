from datetime import datetime
from typing import List

from models import Metric


def collect_power(node_id: str, chassis: dict, timestamp: datetime) -> List[Metric]:
    status = chassis.get("Status", {})

    return [
        Metric(
            node_id,
            timestamp,
            "power",
            "PowerState",
            "Chassis Power State",
            text_value=chassis.get("PowerState"),
            health=status.get("Health"),
            state=status.get("State"),
        )
    ]


def collect_cpu_die_temperatures(
    node_id: str,
    thermal: dict,
    timestamp: datetime,
) -> List[Metric]:
    metrics = []

    for sensor in thermal.get("Temperatures", []):
        member_id = sensor.get("MemberId", "")

        if not member_id.startswith("Die_CPU"):
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


def collect_average_fan_speed(
    node_id: str,
    thermal: dict,
    timestamp: datetime,
) -> List[Metric]:
    readings = [
        fan.get("Reading")
        for fan in thermal.get("Fans", [])
        if fan.get("ReadingUnits") == "RPM"
        and isinstance(fan.get("Reading"), (int, float))
    ]

    if not readings:
        return []

    return [
        Metric(
            node_id,
            timestamp,
            "fan",
            "AverageRPM",
            "Average Fan Speed",
            value=sum(readings) / len(readings),
            unit="RPM",
        )
    ]
