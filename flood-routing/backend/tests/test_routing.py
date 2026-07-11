"""
Sanity tests for the routing engine. Uses a small hand-built graph instead of
a real OSM download, so these run instantly and without internet access —
good for a quick check before a demo.
"""

import networkx as nx
from engine.routing import RoutingEngine


def _build_test_engine():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.000, y=0.000)
    G.add_node(2, x=0.001, y=0.000)
    G.add_node(3, x=0.002, y=0.000)
    # Direct edge 1->3 is deliberately slower than the 1->2->3 path
    G.add_edge(1, 2, key=0, travel_time=10)
    G.add_edge(2, 3, key=0, travel_time=10)
    G.add_edge(1, 3, key=0, travel_time=50)

    engine = RoutingEngine("test-area")
    engine.G = G
    return engine


def test_shortest_path_picks_faster_route():
    engine = _build_test_engine()
    path, travel_time, coords = engine.shortest_path(1, 3)
    assert path == [1, 2, 3]
    assert travel_time == 20
    assert len(coords) == 3


def test_shortest_path_no_route_returns_inf():
    engine = _build_test_engine()
    engine.G.add_node(99, x=1.0, y=1.0)  # disconnected node
    path, travel_time, coords = engine.shortest_path(1, 99)
    assert path is None
    assert travel_time == float("inf")
    assert coords == []


def test_stats_reports_correct_counts():
    engine = _build_test_engine()
    stats = engine.stats()
    assert stats["nodes"] == 3
    assert stats["edges"] == 3  # 1->2, 2->3, and the direct 1->3 edge
