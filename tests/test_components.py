from datetime import datetime, timezone

from redfish.components import (
    collect_average_fan_speed,
    collect_cpu_die_temperatures,
    collect_power,
)


TS = datetime.now(timezone.utc)


def test_collect_power():
    metrics = collect_power(
        "node01",
        {
            "PowerState": "On",
            "Status": {"Health": "OK", "State": "Enabled"},
        },
        TS,
    )

    assert len(metrics) == 1
    assert metrics[0].member_id == "PowerState"
    assert metrics[0].value is None
    assert metrics[0].text_value == "On"
    assert metrics[0].health == "OK"


def test_die_temperature_ignores_core_temperature():
    metrics = collect_cpu_die_temperatures(
        "node01",
        {
            "Temperatures": [
                {
                    "MemberId": "Die_CPU1",
                    "Name": "Die CPU1",
                    "ReadingCelsius": 38.5,
                    "Status": {"Health": "OK", "State": "Enabled"},
                },
                {
                    "MemberId": "Core_0_CPU1",
                    "Name": "Core 0 CPU1",
                    "ReadingCelsius": 44.0,
                    "Status": {"Health": "OK", "State": "Enabled"},
                },
            ]
        },
        TS,
    )

    assert len(metrics) == 1
    assert metrics[0].member_id == "Die_CPU1"
    assert metrics[0].value == 38.5
    # Checking only value is not enough -- a sensor can have the right number
    # and still have the wrong unit or health information (this is exactly
    # what a positional Metric(...) call silently got wrong before).
    assert metrics[0].unit == "C"
    assert metrics[0].health == "OK"
    assert metrics[0].state == "Enabled"
    assert metrics[0].text_value is None


def test_average_fan_speed_uses_rpm_only():
    metrics = collect_average_fan_speed(
        "node01",
        {
            "Fans": [
                {"Reading": 1000, "ReadingUnits": "RPM"},
                {"Reading": 1200, "ReadingUnits": "RPM"},
                {"Reading": 25, "ReadingUnits": "Percent"},
            ]
        },
        TS,
    )

    assert len(metrics) == 1
    assert metrics[0].value == 1100
    assert metrics[0].unit == "RPM"


def test_average_fan_speed_returns_empty_without_rpm():
    metrics = collect_average_fan_speed(
        "node01",
        {
            "Fans": [
                {"Reading": 25, "ReadingUnits": "Percent"},
            ]
        },
        TS,
    )

    assert metrics == []
