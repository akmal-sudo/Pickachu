"""
Sanity tests for FloodSimulator. Same hand-built-graph pattern as
test_routing.py — instant, no OSM download, no internet needed.
"""

import time

import networkx as nx
from engine.routing import RoutingEngine
from engine.flood import FloodSimulator


def _build_test_engine():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.000, y=0.000)
    G.add_node(2, x=0.001, y=0.000)
    G.add_node(3, x=0.002, y=0.000)
    # 1->2->3 is the fast path; 1->3 direct is slower.
    G.add_edge(1, 2, key=0, travel_time=10)
    G.add_edge(2, 3, key=0, travel_time=10)
    G.add_edge(1, 3, key=0, travel_time=50)

    engine = RoutingEngine("test-area")
    engine.G = G
    return engine


def test_flood_edge_increases_travel_time():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    sim.flood_edge(1, 2, 0, depth_cm=40)  # heavy penalty, 20x
    assert engine.G.edges[1, 2, 0]["travel_time"] == 200  # 10 * 20


def test_deep_flood_makes_edge_impassable_and_reroutes():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    sim.flood_edge(1, 2, 0, depth_cm=75)  # >= 60cm -> impassable

    assert engine.G.edges[1, 2, 0]["travel_time"] == float("inf")

    # Shortest path from 1->3 must now avoid the flooded edge and fall back
    # to the direct (slower but passable) 1->3 edge.
    path, travel_time, coords = engine.shortest_path(1, 3)
    assert path == [1, 3]
    assert travel_time == 50


def test_reset_restores_exact_original_values():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    sim.flood_edge(1, 2, 0, depth_cm=75)
    sim.flood_edge(2, 3, 0, depth_cm=15)

    reset_count = sim.reset()

    assert reset_count == 2
    assert engine.G.edges[1, 2, 0]["travel_time"] == 10
    assert engine.G.edges[2, 3, 0]["travel_time"] == 10
    assert "flood_depth_cm" not in engine.G.edges[1, 2, 0]
    assert sim.active_floods() == []


def test_reflooding_same_edge_does_not_corrupt_original():
    """
    Regression test for the exact bug flagged in planning: flooding the same
    edge twice must not overwrite the stored 'original' with an
    already-flooded value.
    """
    engine = _build_test_engine()
    sim = FloodSimulator(engine)

    sim.flood_edge(1, 2, 0, depth_cm=40)   # travel_time now 200
    sim.flood_edge(1, 2, 0, depth_cm=75)   # re-flood deeper -> should still be based on original 10, not 200

    assert engine.G.edges[1, 2, 0]["travel_time"] == float("inf")
    assert sim._original_weights[(1, 2, 0)] == 10  # original preserved, not 200

    sim.reset()
    assert engine.G.edges[1, 2, 0]["travel_time"] == 10


def test_flood_random_respects_n_and_bounds():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    events = sim.flood_random(n=2, min_depth=10, max_depth=80)

    assert len(events) == 2
    for e in events:
        assert 10 <= e["depth_cm"] <= 80
    assert len(sim.active_floods()) == 2


def test_flood_random_caps_n_to_available_edges():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    events = sim.flood_random(n=999)  # only 3 edges exist
    assert len(events) == 3


def test_path_crosses_flood_detects_penalized_but_passable_edge():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    sim.flood_edge(2, 3, 0, depth_cm=15)  # mild, still passable

    path, travel_time, coords = engine.shortest_path(1, 3)
    assert path == [1, 2, 3]  # still the "fast" route despite mild flooding

    crossed = sim.path_crosses_flood(path)
    assert len(crossed) == 1
    assert crossed[0]["depth_cm"] == 15


def test_recompute_after_flood_is_fast():
    """
    Proof of the <1s latency constraint: flooding edges and recomputing a
    route must together stay well under 1 second, even though this is a
    tiny graph — the real assertion matters more once run against the full
    OSM graph, but this locks the behavior in as a regression guard.
    """
    engine = _build_test_engine()
    sim = FloodSimulator(engine)

    start = time.time()
    sim.flood_random(n=2)
    engine.shortest_path(1, 3)
    elapsed_ms = (time.time() - start) * 1000

    assert elapsed_ms < 1000
