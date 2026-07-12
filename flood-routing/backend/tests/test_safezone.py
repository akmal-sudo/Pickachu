"""
Tests for SafeZoneRouter. Same hand-built-graph pattern as the other test
files — fast, no OSM download needed.
"""

import networkx as nx
from engine.routing import RoutingEngine
from engine.flood import FloodSimulator
from engine.safezone import SafeZoneRouter


def _build_test_engine():
    """
    Layout:
        1 (victim) --10--> 2 --10--> 3 (near safe zone A)
                     \
                      --50--> 4 (near safe zone B, only reachable via 1->4 directly)
    """
    G = nx.MultiDiGraph()
    G.graph["crs"] = "epsg:4326"
    G.add_node(1, x=0.000, y=0.000)
    G.add_node(2, x=0.001, y=0.000)
    G.add_node(3, x=0.002, y=0.000)  # safe zone A sits here
    G.add_node(4, x=0.000, y=0.001)  # safe zone B sits here

    G.add_edge(1, 2, key=0, travel_time=10)
    G.add_edge(2, 3, key=0, travel_time=10)
    G.add_edge(1, 4, key=0, travel_time=50)

    engine = RoutingEngine("test-area")
    engine.G = G
    return engine


def _safe_zones():
    return [
        {"name": "Zone A (near node 3)", "lat": 0.000, "lon": 0.002},
        {"name": "Zone B (near node 4)", "lat": 0.001, "lon": 0.000},
    ]


def test_routes_to_nearest_reachable_zone():
    engine = _build_test_engine()
    router = SafeZoneRouter(engine, _safe_zones())

    result = router.route_to_nearest(0.000, 0.000)  # victim at node 1

    assert result["chosen_zone"]["name"] == "Zone A (near node 3)"
    assert result["travel_time_seconds"] == 20  # 10 + 10, cheaper than the 50 direct edge
    assert result["all_zones_unreachable"] is False


def test_falls_back_to_next_nearest_when_closest_is_flooded():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    router = SafeZoneRouter(engine, _safe_zones())

    # Flood the 2->3 edge so Zone A becomes unreachable.
    sim.flood_edge(2, 3, 0, depth_cm=90)

    result = router.route_to_nearest(0.000, 0.000)

    assert result["chosen_zone"]["name"] == "Zone B (near node 4)"
    assert result["travel_time_seconds"] == 50
    assert "Zone A (near node 3)" in result["skipped_zones"]
    assert result["all_zones_unreachable"] is False


def test_all_zones_unreachable_reported_cleanly():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    router = SafeZoneRouter(engine, _safe_zones())

    sim.flood_edge(2, 3, 0, depth_cm=90)
    sim.flood_edge(1, 4, 0, depth_cm=90)

    result = router.route_to_nearest(0.000, 0.000)

    assert result["chosen_zone"] is None
    assert result["all_zones_unreachable"] is True
    assert result["route_coords"] == []


def test_list_zones_returns_all_configured_zones():
    engine = _build_test_engine()
    router = SafeZoneRouter(engine, _safe_zones())
    listed = router.list_zones()
    assert len(listed) == 2
    assert {"name", "lat", "lon"} <= listed[0].keys()
