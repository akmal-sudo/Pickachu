"""
Tests for DispatchEngine. Same hand-built-graph pattern as test_routing.py
and test_flood.py — instant, no OSM download needed.
"""

import networkx as nx
from engine.routing import RoutingEngine
from engine.flood import FloodSimulator
from engine.dispatch import DispatchEngine


def _build_test_engine():
    """
    A small grid:

        1 --- 2 --- 3
        |     |     |
        4 --- 5 --- 6

    Vehicles will start near nodes 1 and 3; victims near nodes 4 and 6.
    The "obviously correct" optimal assignment is vehicle@1 -> victim@4
    and vehicle@3 -> victim@6 (straight down), NOT the crossed alternative.
    """
    G = nx.MultiDiGraph()
    G.graph["crs"] = "epsg:4326"  # ox.nearest_nodes requires this to be set
    G.add_node(1, x=0.000, y=0.001)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.001)
    G.add_node(4, x=0.000, y=0.000)
    G.add_node(5, x=0.001, y=0.000)
    G.add_node(6, x=0.002, y=0.000)

    edges = [(1, 2), (2, 3), (4, 5), (5, 6), (1, 4), (2, 5), (3, 6)]
    for u, v in edges:
        G.add_edge(u, v, key=0, travel_time=10)
        G.add_edge(v, u, key=0, travel_time=10)  # both directions

    engine = RoutingEngine("test-area")
    engine.G = G
    return engine


def test_dispatch_picks_optimal_non_crossing_assignment():
    engine = _build_test_engine()
    dispatch = DispatchEngine(engine)

    vehicles = [[0.001, 0.000], [0.001, 0.002]]  # near node 1, near node 3
    victims = [[0.000, 0.000], [0.000, 0.002]]   # near node 4, near node 6

    result = dispatch.dispatch(vehicles, victims)

    assert len(result["assignments"]) == 2
    assert result["unreachable"] == []
    # Optimal total time should be 2 vehicles x 1 hop (10) = 20, not the
    # crossed alternative which would cost more hops.
    assert result["total_travel_time_seconds"] == 20


def test_dispatch_handles_unequal_vehicle_and_victim_counts():
    engine = _build_test_engine()
    dispatch = DispatchEngine(engine)

    vehicles = [[0.001, 0.000], [0.001, 0.001], [0.001, 0.002]]  # 3 vehicles
    victims = [[0.000, 0.000]]                                    # 1 victim

    result = dispatch.dispatch(vehicles, victims)
    # Only as many assignments as the smaller side allows
    assert len(result["assignments"]) == 1


def test_dispatch_reroutes_around_flooded_edges():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    dispatch = DispatchEngine(engine)

    # Flood the direct 1->4 edge so the vehicle near node 1 must detour.
    sim.flood_edge(1, 4, 0, depth_cm=75)  # impassable

    vehicles = [[0.001, 0.000]]  # near node 1
    victims = [[0.000, 0.000]]   # near node 4

    result = dispatch.dispatch(vehicles, victims)
    assert len(result["assignments"]) == 1
    # Must now be more than the direct 1-hop cost of 10, since it has to detour
    assert result["assignments"][0]["travel_time_seconds"] > 10


def test_dispatch_empty_inputs_returns_empty_result():
    engine = _build_test_engine()
    dispatch = DispatchEngine(engine)

    result = dispatch.dispatch([], [])
    assert result["assignments"] == []
    assert result["total_travel_time_seconds"] == 0
