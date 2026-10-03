from ui.dashboard import ClusterDashboard


def test_resample_pads_short_series_to_graph_width():
    points = [(1, 10.0), (2, 20.0)]
    values = ClusterDashboard._resample(points, 5)

    assert values == [None, None, None, 10.0, 20.0]


def test_resample_reduces_long_series():
    points = [(index, float(index)) for index in range(10)]
    values = ClusterDashboard._resample(points, 5)

    assert len(values) == 5
    assert values[0] == 0.5
    assert values[-1] == 8.5


def test_render_graph_handles_missing_history():
    rendered = ClusterDashboard._render_graph(
        "CPU temperature",
        [("CPU1", [])],
        " C",
    )

    assert "No history collected yet" in rendered
